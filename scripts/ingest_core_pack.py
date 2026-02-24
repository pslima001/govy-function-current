#!/usr/bin/env python3
"""
Ingere leis/decretos core que estao presentes no blob raw.

Le o federal_core_manifest.json, identifica quais core docs existem
no blob storage, e roda o pipeline (extract → chunk → write DB)
para cada um que ainda nao estiver no DB.

Uso:
  python scripts/ingest_core_pack.py [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from govy.legal.pipeline import process_one, _get_container, RAW_CONTAINER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_core_pack")

MANIFEST_PATH = Path(__file__).parent.parent / "normas-juridicas-registry" / "federal" / "federal_core_manifest.json"


def get_existing_doc_ids():
    """Retorna set de doc_ids ja presentes no DB."""
    import psycopg2
    connstr = os.environ.get(
        "POSTGRES_CONNSTR",
        "host=pg-govy-legal.postgres.database.azure.com port=5432 dbname=govy_legal user=govyadmin password=s39VebZSTag8I9VU6xHCN8w3zMgQ sslmode=require",
    )
    conn = psycopg2.connect(connstr)
    cur = conn.cursor()
    cur.execute("SELECT doc_id FROM legal_document")
    ids = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return ids


def find_blob_for_doc(doc_id: str, doc_type: str) -> str | None:
    """
    Busca blob path para um doc_id no container raw.

    Blob convention: federal/BR/{tipo_plural}/{doc_id}/source.{pdf|docx}
    """
    type_to_folder = {
        "lei": "leis",
        "lei_complementar": "leis_complementares",
        "decreto": "decretos",
        "instrucao_normativa": "instrucoes_normativas",
        "portaria": "portarias",
        "resolucao": "resolucoes",
        "medida_provisoria": "medidas_provisorias",
        "emenda_constitucional": "emendas_constitucionais",
    }
    folder = type_to_folder.get(doc_type, doc_type + "s")
    prefix = f"federal/BR/{folder}/{doc_id}/"

    container = _get_container()
    blobs = list(container.list_blobs(name_starts_with=prefix))
    for blob in blobs:
        if blob.name.lower().endswith((".pdf", ".docx")):
            return blob.name
    return None


def main():
    parser = argparse.ArgumentParser(description="Ingest core federal laws from blob to DB")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if already in DB")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        logger.error("Manifest not found: %s", MANIFEST_PATH)
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    core_laws = manifest.get("core_laws", [])
    existing = get_existing_doc_ids()

    logger.info("=== Core Pack Ingest ===")
    logger.info("Manifest: %d core laws", len(core_laws))
    logger.info("Existing in DB: %d doc_ids", len(existing))

    results = []

    for law in core_laws:
        doc_id = law["doc_id"]
        title = law["title"]
        doc_type = law["doc_type"]

        # Skip if already in DB and not forcing
        if doc_id in existing and not args.force:
            logger.info("[SKIP] %s — already in DB", doc_id)
            results.append({"doc_id": doc_id, "status": "already_in_db"})
            continue

        # Find blob
        blob_name = find_blob_for_doc(doc_id, doc_type)
        if not blob_name:
            logger.warning("[MISSING] %s — no blob found in raw", doc_id)
            results.append({"doc_id": doc_id, "status": "no_blob"})
            continue

        # Ingest
        logger.info("[INGEST] %s — blob: %s", doc_id, blob_name)
        try:
            registry_entry = {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "number": law.get("number"),
                "year": law.get("year"),
                "title": title,
                "title_short": title.split(" - ")[0] if " - " in title else title,
            }
            result = process_one(
                blob_name=blob_name,
                dry_run=args.dry_run,
                registry_entry=registry_entry,
            )
            results.append(result)
            logger.info("  Result: %s — %d provisions, %d chunks",
                        result.get("status"), result.get("provisions", 0), result.get("chunks", 0))
        except Exception as e:
            logger.exception("  ERROR: %s", e)
            results.append({"doc_id": doc_id, "status": "error", "error": str(e)})

    # Summary
    ingested = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "already_in_db")
    missing = sum(1 for r in results if r.get("status") == "no_blob")
    errors = sum(1 for r in results if r.get("status") == "error")

    logger.info("=== Summary ===")
    logger.info("  Ingested: %d", ingested)
    logger.info("  Already in DB: %d", skipped)
    logger.info("  No blob (missing): %d", missing)
    logger.info("  Errors: %d", errors)

    # Save results
    out_path = "outputs/core_pack_ingest_report.json"
    os.makedirs("outputs", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Report: %s", out_path)


if __name__ == "__main__":
    main()
