#!/usr/bin/env python3
"""
Upload core federal law PDFs from local drop folder to Azure Blob Storage.

Reads the federal_core_manifest.json to know which docs are missing,
scans the drop folder for matching PDFs, and uploads each one to the
standard blob path convention.

Drop folder: C:\\Users\\INTEL\\OneDrive\\Area de Trabalho\\Legislacao\\Federal_Core_Pack\\
Expected filenames: lei_8666_1993.pdf, decreto_10024_2019.pdf, lc_123_2006.pdf, etc.

Blob path convention:
  normas-juridicas-raw/federal/BR/{tipo_plural}/{doc_id}/source.pdf

Usage:
  python scripts/upload_core_pack.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.storage.blob import BlobServiceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("upload_core_pack")

DROP_FOLDER = Path(r"C:\Users\INTEL\OneDrive\Área de Trabalho\Legislação\Federal_Core_Pack")
MANIFEST_PATH = Path(__file__).parent.parent / "normas-juridicas-registry" / "federal" / "federal_core_manifest.json"
CONTAINER = "normas-juridicas-raw"

# doc_type → blob folder name
TYPE_TO_FOLDER = {
    "lei": "leis",
    "lei_complementar": "leis_complementares",
    "decreto": "decretos",
    "instrucao_normativa": "instrucoes_normativas",
    "portaria": "portarias",
    "resolucao": "resolucoes",
    "medida_provisoria": "medidas_provisorias",
    "emenda_constitucional": "emendas_constitucionais",
}


def get_blob_service():
    connstr = os.environ.get("AZURE_STORAGE_CONNSTR_SPONSOR", "")
    if not connstr:
        logger.error("AZURE_STORAGE_CONNSTR_SPONSOR not set")
        sys.exit(1)
    return BlobServiceClient.from_connection_string(connstr)


def build_expected_filename(doc_id: str) -> str:
    """Build expected local filename from doc_id: lei_8666_1993_federal_br → lei_8666_1993.pdf"""
    # Strip _federal_br suffix
    base = doc_id.replace("_federal_br", "")
    return f"{base}.pdf"


def build_blob_path(doc_id: str, doc_type: str) -> str:
    """Build blob path: federal/BR/leis/lei_8666_1993_federal_br/source.pdf"""
    folder = TYPE_TO_FOLDER.get(doc_type, doc_type + "s")
    return f"federal/BR/{folder}/{doc_id}/source.pdf"


def main():
    parser = argparse.ArgumentParser(description="Upload core law PDFs to blob storage")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually upload")
    args = parser.parse_args()

    # Load manifest
    if not MANIFEST_PATH.exists():
        logger.error("Manifest not found: %s", MANIFEST_PATH)
        sys.exit(1)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    missing = [law for law in manifest["core_laws"] if law["status"] == "missing"]
    logger.info("=== Upload Core Pack ===")
    logger.info("Missing in manifest: %d", len(missing))
    logger.info("Drop folder: %s", DROP_FOLDER)

    if not DROP_FOLDER.exists():
        logger.error("Drop folder does not exist: %s", DROP_FOLDER)
        sys.exit(1)

    # Scan drop folder
    local_pdfs = {f.name.lower(): f for f in DROP_FOLDER.iterdir() if f.suffix.lower() == ".pdf"}
    logger.info("PDFs found in drop folder: %d", len(local_pdfs))
    for name in sorted(local_pdfs.keys()):
        logger.info("  %s (%d KB)", name, local_pdfs[name].stat().st_size // 1024)

    if not local_pdfs:
        logger.warning("No PDFs in drop folder. Place PDFs and re-run.")
        print("\nExpected filenames:")
        for law in missing:
            expected = build_expected_filename(law["doc_id"])
            print(f"  {expected}  ←  {law['title']}")
        return

    # Match and upload
    svc = get_blob_service() if not args.dry_run else None
    container = svc.get_container_client(CONTAINER) if svc else None

    uploaded = 0
    not_found = 0
    already = 0

    for law in missing:
        doc_id = law["doc_id"]
        doc_type = law["doc_type"]
        expected_name = build_expected_filename(doc_id)
        blob_path = build_blob_path(doc_id, doc_type)

        local_file = local_pdfs.get(expected_name.lower())
        if not local_file:
            logger.warning("[NOT FOUND] %s — expected %s", doc_id, expected_name)
            not_found += 1
            continue

        file_size = local_file.stat().st_size
        if file_size < 1000:
            logger.warning("[TOO SMALL] %s — %d bytes, skipping", doc_id, file_size)
            not_found += 1
            continue

        if args.dry_run:
            logger.info("[DRY RUN] %s → %s/%s (%d KB)", doc_id, CONTAINER, blob_path, file_size // 1024)
            uploaded += 1
            continue

        # Check if blob already exists
        blob_client = container.get_blob_client(blob_path)
        if blob_client.exists():
            logger.info("[ALREADY EXISTS] %s → %s", doc_id, blob_path)
            already += 1
            continue

        # Upload
        logger.info("[UPLOADING] %s → %s/%s (%d KB)", doc_id, CONTAINER, blob_path, file_size // 1024)
        with open(local_file, "rb") as data:
            blob_client.upload_blob(data, overwrite=False, content_settings=None)
        logger.info("[OK] %s uploaded", doc_id)
        uploaded += 1

    logger.info("=== Summary ===")
    logger.info("  Uploaded: %d", uploaded)
    logger.info("  Already in blob: %d", already)
    logger.info("  Not found in drop: %d", not_found)
    logger.info("  Dry run: %s", args.dry_run)

    if uploaded > 0 and not args.dry_run:
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. python scripts/ingest_core_pack.py")
        logger.info("  2. python scripts/run_extractors.py")


if __name__ == "__main__":
    main()
