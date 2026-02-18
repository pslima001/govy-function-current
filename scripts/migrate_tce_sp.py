"""Migrate TCE-SP blobs from legacy container to juris-raw standard.

Server-side copy (no download/upload) from:
  sttcejurisprudencia/tce-jurisprudencia/tce-sp/...
to:
  sttcejurisprudencia/juris-raw/tce-sp/...

Idempotent: skips blobs that already exist with the same size.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONTAINER_LEGACY = "tce-jurisprudencia"
CONTAINER_NEW = "juris-raw"
PREFIX_LEGACY = "tce-sp/"
PREFIX_NEW = "tce-sp/"
REPORT_PATH = "outputs/migrate_tce_sp_report.json"
LOG_INTERVAL = 1000


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    conn = os.environ.get("TCE_STORAGE_CONNECTION") or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        # Fall back to account key via az cli
        account = "sttcejurisprudencia"
        logger.info(f"No connection string found, trying account key for {account}")
        import subprocess

        result = subprocess.run(
            [
                "az",
                "storage",
                "account",
                "keys",
                "list",
                "--account-name",
                account,
                "--query",
                "[0].value",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"Failed to get account key: {result.stderr}")
            return 1
        key = result.stdout.strip()
        conn = f"DefaultEndpointsProtocol=https;AccountName={account};AccountKey={key};EndpointSuffix=core.windows.net"

    blob_service = BlobServiceClient.from_connection_string(conn)
    legacy = blob_service.get_container_client(CONTAINER_LEGACY)
    new = blob_service.get_container_client(CONTAINER_NEW)

    # List legacy blobs
    logger.info(f"Listing blobs in {CONTAINER_LEGACY}/{PREFIX_LEGACY}...")
    legacy_blobs = []
    for blob in legacy.list_blobs(name_starts_with=PREFIX_LEGACY):
        legacy_blobs.append({"name": blob.name, "size": blob.size})
    logger.info(f"Found {len(legacy_blobs)} blobs in legacy container")

    # List existing blobs in new container (for skip logic)
    logger.info(f"Listing existing blobs in {CONTAINER_NEW}/{PREFIX_NEW}...")
    existing = {}
    for blob in new.list_blobs(name_starts_with=PREFIX_NEW):
        existing[blob.name] = blob.size
    logger.info(f"Found {len(existing)} blobs already in new container")

    copied = 0
    skipped = 0
    failed = 0
    bytes_copied = 0
    start_time = time.time()

    for i, blob_info in enumerate(legacy_blobs):
        src_name = blob_info["name"]
        dst_name = src_name  # same path structure
        size = blob_info["size"]

        # Skip if already exists with same size
        if dst_name in existing and existing[dst_name] == size:
            skipped += 1
            if (i + 1) % LOG_INTERVAL == 0:
                logger.info(
                    f"Progress: {i + 1}/{len(legacy_blobs)} (copied={copied} skipped={skipped} failed={failed})"
                )
            continue

        try:
            src_blob = legacy.get_blob_client(src_name)
            dst_blob = new.get_blob_client(dst_name)
            dst_blob.start_copy_from_url(src_blob.url)
            copied += 1
            bytes_copied += size
        except Exception as e:
            logger.error(f"Failed to copy {src_name}: {e}")
            failed += 1

        if (i + 1) % LOG_INTERVAL == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Progress: {i + 1}/{len(legacy_blobs)} "
                f"(copied={copied} skipped={skipped} failed={failed} "
                f"elapsed={elapsed:.0f}s)"
            )

    elapsed = time.time() - start_time
    logger.info(
        f"Migration complete: total={len(legacy_blobs)} copied={copied} "
        f"skipped={skipped} failed={failed} bytes_copied={bytes_copied} "
        f"elapsed={elapsed:.1f}s"
    )

    # Build report
    report = {
        "kind": "migration_report",
        "generated_at": _utc_now_iso(),
        "source": f"{CONTAINER_LEGACY}/{PREFIX_LEGACY}",
        "destination": f"{CONTAINER_NEW}/{PREFIX_NEW}",
        "summary": {
            "total_legacy": len(legacy_blobs),
            "copied": copied,
            "skipped": skipped,
            "failed": failed,
            "bytes_copied": bytes_copied,
            "elapsed_seconds": round(elapsed, 1),
        },
        "sample_paths": [b["name"] for b in legacy_blobs[:5]],
    }

    os.makedirs(os.path.dirname(REPORT_PATH) or ".", exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Report saved to {REPORT_PATH}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
