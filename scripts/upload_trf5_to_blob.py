#!/usr/bin/env python3
"""
upload_trf5_to_blob.py — Upload 16.860 TRF5 JSONs para Azure Blob Storage.

Source: C:\\Users\\INTEL\\Downloads\\trf5_output\\{year}\\*.json
Dest:   sttcejurisprudencia / juris-raw / trf5/acordaos/{filename}.json

Usage:
  # Dry-run (conta mas nao faz upload)
  python scripts/upload_trf5_to_blob.py --dry-run

  # Run completo (skip existing por padrao)
  python scripts/upload_trf5_to_blob.py

  # Forcar re-upload
  python scripts/upload_trf5_to_blob.py --no-skip-existing
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from azure.storage.blob import BlobServiceClient, ContentSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("upload-trf5")

for noisy in ("azure.core.pipeline.policies", "azure.storage", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Config
LOCAL_BASE = Path(r"C:\Users\INTEL\Downloads\trf5_output")
ACCOUNT_NAME = "sttcejurisprudencia"
CONTAINER = "juris-raw"
BLOB_PREFIX = "trf5/acordaos/"
LOG_INTERVAL = 500


def _get_conn_string() -> str:
    conn = os.environ.get("TCE_STORAGE_CONNECTION")
    if conn:
        return conn
    log.info(f"No TCE_STORAGE_CONNECTION, trying az CLI key for {ACCOUNT_NAME}...")
    cmd = (
        f'az storage account keys list'
        f' --account-name {ACCOUNT_NAME}'
        f' --query "[0].value" -o tsv'
    )
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        log.error(f"Failed to get key: {result.stderr}")
        sys.exit(1)
    key = result.stdout.strip()
    return (
        f"DefaultEndpointsProtocol=https;AccountName={ACCOUNT_NAME};"
        f"AccountKey={key};EndpointSuffix=core.windows.net"
    )


def _collect_local_files() -> list[Path]:
    """Coleta todos os JSONs locais, ordenados por ano."""
    files = []
    for year_dir in sorted(LOCAL_BASE.iterdir()):
        if year_dir.is_dir():
            for f in sorted(year_dir.glob("*.json")):
                files.append(f)
    return files


def run(dry_run: bool = False, skip_existing: bool = True):
    local_files = _collect_local_files()
    log.info(f"Found {len(local_files):,} local JSON files")

    if dry_run:
        for year_dir in sorted(LOCAL_BASE.iterdir()):
            if year_dir.is_dir():
                c = len(list(year_dir.glob("*.json")))
                log.info(f"  {year_dir.name}: {c:,}")
        log.info(f"[DRY-RUN] Would upload {len(local_files):,} files to {CONTAINER}/{BLOB_PREFIX}")
        return

    conn = _get_conn_string()
    service = BlobServiceClient.from_connection_string(conn)
    container = service.get_container_client(CONTAINER)

    # List existing blobs for skip logic
    existing = set()
    if skip_existing:
        log.info(f"Listing existing blobs in {CONTAINER}/{BLOB_PREFIX}...")
        for blob in container.list_blobs(name_starts_with=BLOB_PREFIX):
            existing.add(blob.name)
        log.info(f"Found {len(existing):,} existing blobs")

    uploaded = 0
    skipped = 0
    errors = 0
    start = time.time()

    for i, fp in enumerate(local_files):
        blob_name = f"{BLOB_PREFIX}{fp.name}"

        if skip_existing and blob_name in existing:
            skipped += 1
            if (i + 1) % LOG_INTERVAL == 0:
                elapsed = time.time() - start
                rate = (uploaded + skipped) / (elapsed / 60) if elapsed > 0 else 0
                log.info(f"Progress: {i+1:,}/{len(local_files):,} (up={uploaded:,} skip={skipped:,} err={errors}) {rate:.0f}/min")
            continue

        try:
            with open(fp, "rb") as f:
                data = f.read()
            container.get_blob_client(blob_name).upload_blob(
                data,
                overwrite=False,
                content_settings=ContentSettings(
                    content_type="application/json; charset=utf-8"
                ),
            )
            uploaded += 1
        except Exception as e:
            if "BlobAlreadyExists" in str(e):
                skipped += 1
            else:
                errors += 1
                if errors <= 10:
                    log.error(f"Upload failed {blob_name}: {e}")

        if (i + 1) % LOG_INTERVAL == 0:
            elapsed = time.time() - start
            rate = (uploaded + skipped) / (elapsed / 60) if elapsed > 0 else 0
            log.info(f"Progress: {i+1:,}/{len(local_files):,} (up={uploaded:,} skip={skipped:,} err={errors}) {rate:.0f}/min")

    elapsed = time.time() - start
    log.info("=" * 60)
    log.info(f"UPLOAD COMPLETE: trf5")
    log.info(f"  Total files:  {len(local_files):,}")
    log.info(f"  Uploaded:     {uploaded:,}")
    log.info(f"  Skipped:      {skipped:,}")
    log.info(f"  Errors:       {errors}")
    log.info(f"  Elapsed:      {elapsed:.1f}s")
    log.info("=" * 60)

    # Verify
    log.info("Verifying blob count...")
    count = sum(1 for _ in container.list_blobs(name_starts_with=BLOB_PREFIX))
    log.info(f"Blobs in {CONTAINER}/{BLOB_PREFIX}: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Upload TRF5 JSONs to Azure Blob")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no upload")
    parser.add_argument("--no-skip-existing", action="store_true", help="Re-upload existing")
    args = parser.parse_args()

    run(dry_run=args.dry_run, skip_existing=not args.no_skip_existing)


if __name__ == "__main__":
    main()
