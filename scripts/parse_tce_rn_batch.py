#!/usr/bin/env python3
"""
parse_tce_rn_batch.py — Batch parser para TCE-RN (41.753 JSONs inline → kb-raw)

Le blobs JSON de juris-raw/tce-rn/acordaos/ (sttcejurisprudencia),
parseia com tce_rn_parser, transforma via mapping_tce_to_kblegal,
e grava envelopes JSON em kb-raw/ (stgovyparsetestsponsor).

Usage:
  # Dry-run com 5 items (nao grava nada)
  python scripts/parse_tce_rn_batch.py --dry-run --limit 5

  # Run completo (skip existing por padrao)
  python scripts/parse_tce_rn_batch.py

  # Forcar reprocessamento (sem skip)
  python scripts/parse_tce_rn_batch.py --no-skip-existing

Environment:
  TCE_STORAGE_CONNECTION    — conn string para sttcejurisprudencia (juris-raw)
  GOVY_STORAGE_CONNECTION   — conn string para stgovyparsetestsponsor (kb-raw)
  (fallback: az CLI account key lookup)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from azure.storage.blob import BlobServiceClient, ContentSettings

from govy.api.mapping_tce_to_kblegal import (
    transform_parser_to_kblegal,
    validate_kblegal_doc,
)
from govy.api.tce_rn_parser import parse_tce_rn_json
from govy.config.tribunal_registry import get_config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("parse-tce-rn")

for noisy in ("azure.core.pipeline.policies", "azure.storage", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRIBUNAL_ID = "tce-rn"
RAW_ACCOUNT = "sttcejurisprudencia"
RAW_CONTAINER = "juris-raw"
RAW_PREFIX = "tce-rn/acordaos/"

PARSED_ACCOUNT = "stgovyparsetestsponsor"
KB_RAW_CONTAINER = "kb-raw"

REPORT_DIR = Path("outputs")
LOG_INTERVAL = 500
EXCEPTION_PREFIX = "_exceptions/"


# ---------------------------------------------------------------------------
# Azure helpers
# ---------------------------------------------------------------------------

def _get_conn_string(env_var: str, account_name: str) -> str:
    """Get connection string from env var or fall back to az CLI key lookup."""
    conn = os.environ.get(env_var)
    if conn:
        return conn
    log.info(f"No {env_var} found, trying az CLI key for {account_name}...")
    cmd = (
        f'az storage account keys list'
        f' --account-name {account_name}'
        f' --query "[0].value" -o tsv'
    )
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        log.error(f"Failed to get key for {account_name}: {result.stderr}")
        sys.exit(1)
    key = result.stdout.strip()
    return (
        f"DefaultEndpointsProtocol=https;AccountName={account_name};"
        f"AccountKey={key};EndpointSuffix=core.windows.net"
    )


def _blob_path_to_json_key(blob_name: str) -> str:
    """
    Converte path do blob raw para nome do JSON em kb-raw.
    Ex: tce-rn/acordaos/tce-rn--12345.json → tce-rn--acordaos--tce-rn--12345.json
    """
    name = blob_name.rsplit(".", 1)[0]
    name = name.replace("/", "--")
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return f"{name}.json"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(
    dry_run: bool = False,
    limit: int = 0,
    skip_existing: bool = True,
) -> dict:
    cfg = get_config(TRIBUNAL_ID)

    # --- Connect to storage ---
    raw_conn = _get_conn_string("TCE_STORAGE_CONNECTION", RAW_ACCOUNT)
    raw_service = BlobServiceClient.from_connection_string(raw_conn)
    raw_container = raw_service.get_container_client(RAW_CONTAINER)

    if not dry_run:
        parsed_conn = _get_conn_string("GOVY_STORAGE_CONNECTION", PARSED_ACCOUNT)
        parsed_service = BlobServiceClient.from_connection_string(parsed_conn)
        kb_container = parsed_service.get_container_client(KB_RAW_CONTAINER)
    else:
        kb_container = None

    # --- List source blobs ---
    log.info(f"Listing blobs in {RAW_CONTAINER}/{RAW_PREFIX}...")
    source_blobs = []
    for blob in raw_container.list_blobs(name_starts_with=RAW_PREFIX):
        if blob.name.endswith(".json"):
            source_blobs.append(blob.name)
    log.info(f"Found {len(source_blobs):,} source JSONs")

    # --- List existing kb-raw blobs (for skip logic) ---
    existing_keys = set()
    if skip_existing and not dry_run:
        log.info(f"Listing existing blobs in {KB_RAW_CONTAINER}/tce-rn--...")
        for blob in kb_container.list_blobs(name_starts_with="tce-rn--"):
            existing_keys.add(blob.name)
        log.info(f"Found {len(existing_keys):,} existing kb-raw blobs")

    # --- Apply limit ---
    if limit > 0:
        source_blobs = source_blobs[:limit]
        log.info(f"Limited to {len(source_blobs)} items")

    # --- Process ---
    stats = {
        "total": len(source_blobs),
        "parsed": 0,
        "skipped_existing": 0,
        "skipped_no_content": 0,
        "validation_errors": 0,
        "upload_errors": 0,
        "exceptions": [],
    }
    samples = []
    start_time = time.time()

    for i, blob_name in enumerate(source_blobs):
        json_key = _blob_path_to_json_key(blob_name)

        # Skip existing
        if skip_existing and json_key in existing_keys:
            stats["skipped_existing"] += 1
            if (i + 1) % LOG_INTERVAL == 0:
                _log_progress(i + 1, stats, start_time)
            continue

        # 1. Download blob
        try:
            blob_data = raw_container.get_blob_client(blob_name).download_blob().readall()
            data = json.loads(blob_data)
        except Exception as e:
            log.error(f"Failed to read {blob_name}: {e}")
            stats["exceptions"].append({"blob": blob_name, "error": f"read: {e}"})
            stats["upload_errors"] += 1
            continue

        # 2. Parse
        try:
            parser_output = parse_tce_rn_json(data)
        except Exception as e:
            log.error(f"Parse failed for {blob_name}: {e}")
            stats["exceptions"].append({"blob": blob_name, "error": f"parse: {e}"})
            stats["upload_errors"] += 1
            continue

        # 3. Transform to kb-legal
        try:
            kb_doc = transform_parser_to_kblegal(
                parser_output, blob_name, config=cfg,
            )
        except Exception as e:
            log.error(f"Mapping failed for {blob_name}: {e}")
            stats["exceptions"].append({"blob": blob_name, "error": f"mapping: {e}"})
            stats["upload_errors"] += 1
            continue

        if not kb_doc:
            stats["skipped_no_content"] += 1
            continue

        # 4. Validate
        errors = validate_kblegal_doc(kb_doc)
        if errors:
            log.warning(f"Validation errors for {blob_name}: {errors}")
            stats["validation_errors"] += 1
            stats["exceptions"].append({
                "blob": blob_name, "error": f"validation: {errors}",
            })
            # Continue anyway — validation errors are warnings, not blockers

        # 5. Build envelope
        envelope = {
            "kb_doc": kb_doc,
            "metadata": {
                "blob_path": blob_name,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "parser_version": "tce_rn_parser_v1",
                "mapping_version": "mapping_tce_to_kblegal_v1",
                "source_mode": "import_json",
            },
            "parser_raw": {
                k: v for k, v in parser_output.items()
                if k not in ("text", "text_1")
            },
        }

        # 6. Upload (or dry-run log)
        if dry_run:
            log.info(f"[DRY-RUN] Would write kb-raw/{json_key}")
            log.info(f"  chunk_id: {kb_doc.get('chunk_id')}")
            log.info(f"  title: {kb_doc.get('title')}")
            log.info(f"  content len: {len(kb_doc.get('content', ''))}")
            log.info(f"  fields: {len(kb_doc)}/19")
            log.info(f"  validation: {'PASS' if not errors else errors}")
            stats["parsed"] += 1
            if len(samples) < 5:
                samples.append({"json_key": json_key, "kb_doc": kb_doc})
        else:
            try:
                kb_container.get_blob_client(json_key).upload_blob(
                    json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8"),
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type="application/json; charset=utf-8"
                    ),
                )
                stats["parsed"] += 1
            except Exception as e:
                log.error(f"Upload failed for {json_key}: {e}")
                stats["upload_errors"] += 1
                stats["exceptions"].append({
                    "blob": blob_name, "error": f"upload: {e}",
                })

        if (i + 1) % LOG_INTERVAL == 0:
            _log_progress(i + 1, stats, start_time)

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 1)
    stats["rate_per_min"] = round(stats["parsed"] / (elapsed / 60), 1) if elapsed > 0 else 0

    # --- Final report ---
    log.info("=" * 60)
    log.info(f"COMPLETE: {TRIBUNAL_ID}")
    log.info(f"  Total source blobs: {stats['total']:,}")
    log.info(f"  Parsed & uploaded:  {stats['parsed']:,}")
    log.info(f"  Skipped (existing): {stats['skipped_existing']:,}")
    log.info(f"  Skipped (no content): {stats['skipped_no_content']:,}")
    log.info(f"  Validation errors:  {stats['validation_errors']:,}")
    log.info(f"  Upload errors:      {stats['upload_errors']:,}")
    log.info(f"  Elapsed: {elapsed:.1f}s ({stats['rate_per_min']}/min)")
    log.info("=" * 60)

    # Save report
    report = {
        "kind": "parse_batch_report",
        "tribunal_id": TRIBUNAL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "stats": {k: v for k, v in stats.items() if k != "exceptions"},
        "exception_count": len(stats["exceptions"]),
        "exceptions_sample": stats["exceptions"][:20],
    }
    if dry_run and samples:
        report["samples"] = samples

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"parse_tce_rn_{'dryrun' if dry_run else 'batch'}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log.info(f"Report saved to {report_path}")

    # Save exceptions to kb-raw if not dry run
    if not dry_run and stats["exceptions"]:
        try:
            exc_key = f"{EXCEPTION_PREFIX}tce-rn_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            kb_container.get_blob_client(exc_key).upload_blob(
                json.dumps(stats["exceptions"], ensure_ascii=False, indent=2).encode("utf-8"),
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="application/json; charset=utf-8"
                ),
            )
            log.info(f"Exceptions saved to kb-raw/{exc_key}")
        except Exception as e:
            log.warning(f"Could not save exceptions to blob: {e}")

    return stats


def _log_progress(current: int, stats: dict, start_time: float):
    elapsed = time.time() - start_time
    rate = current / (elapsed / 60) if elapsed > 0 else 0
    log.info(
        f"Progress: {current:,}/{stats['total']:,} "
        f"(parsed={stats['parsed']:,} skip_exist={stats['skipped_existing']:,} "
        f"skip_empty={stats['skipped_no_content']:,} err={stats['upload_errors']:,}) "
        f"{rate:.0f}/min"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch parser TCE-RN: juris-raw JSONs → kb-raw"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nao grava nada, so loga output",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Processa apenas N items (0 = todos)",
    )
    parser.add_argument(
        "--no-skip-existing", action="store_true",
        help="Reprocessa items ja existentes em kb-raw",
    )
    args = parser.parse_args()

    stats = run(
        dry_run=args.dry_run,
        limit=args.limit,
        skip_existing=not args.no_skip_existing,
    )

    # Exit code
    if stats["upload_errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
