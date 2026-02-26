#!/usr/bin/env python3
"""
parse_tce_rs_batch.py — Batch parser para TCE-RS (5.488 PDFs -> kb-raw)

Le blobs PDF de juris-raw/tce-rs/acordaos/ (sttcejurisprudencia),
parseia com tce_parser_v3, merge com metadata JSON do scraper,
transforma via mapping_tce_to_kblegal,
e grava envelopes JSON em kb-raw/tce-rs/ (stgovyparsetestsponsor).

Usage:
  # Dry-run com 5 items
  python scripts/parse_tce_rs_batch.py --dry-run --limit 5

  # Run completo (skip existing por padrao)
  python scripts/parse_tce_rs_batch.py

  # Audit 30 amostras apos run
  python scripts/parse_tce_rs_batch.py --audit-only

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
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from azure.storage.blob import BlobServiceClient, ContentSettings

from govy.api.mapping_tce_to_kblegal import (
    transform_parser_to_kblegal,
    validate_kblegal_doc,
)
from govy.api.tce_parser_v3 import parse_pdf_bytes, merge_with_scraper_metadata
from govy.api.tce_queue_handler import _normalize_scraper_fields
from govy.config.tribunal_registry import get_config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("parse-tce-rs")

for noisy in ("azure.core.pipeline.policies", "azure.storage", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRIBUNAL_ID = "tce-rs"
RAW_ACCOUNT = "sttcejurisprudencia"
RAW_CONTAINER = "juris-raw"
RAW_PREFIX = "tce-rs/acordaos/"

PARSED_ACCOUNT = "stgovyparsetestsponsor"
KB_RAW_CONTAINER = "kb-raw"
PARSED_PREFIX = "tce-rs/"

REPORT_DIR = Path("outputs")
LOG_INTERVAL = 200
EXCEPTION_PREFIX = "_exceptions/"
REPORT_BLOB_PREFIX = "_reports/"


# ---------------------------------------------------------------------------
# Azure helpers
# ---------------------------------------------------------------------------

def _get_conn_string(env_var: str, account_name: str) -> str:
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


def _pdf_blob_to_doc_id(blob_name: str) -> str:
    """
    tce-rs/acordaos/tce-rs--PRE--1000078--5259772.pdf -> tce-rs--PRE--1000078--5259772
    """
    filename = blob_name.rsplit("/", 1)[-1]
    return filename.rsplit(".", 1)[0]


def _doc_id_to_kb_key(doc_id: str) -> str:
    return f"{PARSED_PREFIX}{doc_id}.json"


def _doc_id_to_meta_blob(doc_id: str) -> str:
    return f"{RAW_PREFIX}{doc_id}.json"


# ---------------------------------------------------------------------------
# Main parse logic
# ---------------------------------------------------------------------------

def run(
    dry_run: bool = False,
    limit: int = 0,
    skip_existing: bool = True,
) -> dict:
    cfg = get_config(TRIBUNAL_ID)

    # --- Connect ---
    raw_conn = _get_conn_string("TCE_STORAGE_CONNECTION", RAW_ACCOUNT)
    raw_service = BlobServiceClient.from_connection_string(raw_conn)
    raw_container = raw_service.get_container_client(RAW_CONTAINER)

    if not dry_run:
        parsed_conn = _get_conn_string("GOVY_STORAGE_CONNECTION", PARSED_ACCOUNT)
        parsed_service = BlobServiceClient.from_connection_string(parsed_conn)
        kb_container = parsed_service.get_container_client(KB_RAW_CONTAINER)
    else:
        kb_container = None

    # --- List source PDFs (skip _relatorio.pdf) ---
    log.info(f"Listing PDFs in {RAW_CONTAINER}/{RAW_PREFIX}...")
    source_pdfs = []
    for blob in raw_container.list_blobs(name_starts_with=RAW_PREFIX):
        if blob.name.endswith(".pdf") and not blob.name.endswith("_relatorio.pdf"):
            source_pdfs.append(blob.name)
    log.info(f"Found {len(source_pdfs):,} decisao PDFs")

    # --- List existing kb-raw blobs ---
    existing_keys = set()
    if skip_existing and not dry_run:
        log.info(f"Listing existing blobs in {KB_RAW_CONTAINER}/{PARSED_PREFIX}...")
        for blob in kb_container.list_blobs(name_starts_with=PARSED_PREFIX):
            existing_keys.add(blob.name)
        log.info(f"Found {len(existing_keys):,} existing kb-raw blobs")

    # --- Apply limit ---
    if limit > 0:
        source_pdfs = source_pdfs[:limit]
        log.info(f"Limited to {len(source_pdfs)} items")

    # --- Process ---
    stats = {
        "total": len(source_pdfs),
        "parsed": 0,
        "skipped_existing": 0,
        "terminal_no_text": 0,
        "skipped_no_content": 0,
        "validation_errors": 0,
        "upload_errors": 0,
        "exceptions": [],
    }
    start_time = time.time()

    for i, pdf_blob in enumerate(source_pdfs):
        doc_id = _pdf_blob_to_doc_id(pdf_blob)
        kb_key = _doc_id_to_kb_key(doc_id)

        # Skip existing
        if skip_existing and kb_key in existing_keys:
            stats["skipped_existing"] += 1
            if (i + 1) % LOG_INTERVAL == 0:
                _log_progress(i + 1, stats, start_time)
            continue

        # 1. Download PDF
        try:
            pdf_bytes = raw_container.get_blob_client(pdf_blob).download_blob().readall()
        except Exception as e:
            log.error(f"Failed to download {pdf_blob}: {e}")
            stats["exceptions"].append({"blob": pdf_blob, "error": f"download: {e}"})
            stats["upload_errors"] += 1
            continue

        if len(pdf_bytes) < 100:
            stats["terminal_no_text"] += 1
            stats["exceptions"].append({
                "blob": pdf_blob, "error": "pdf_too_small",
                "size": len(pdf_bytes),
            })
            continue

        # 2. Parse PDF (include_text=True for full_text strategy)
        try:
            parser_output = parse_pdf_bytes(pdf_bytes, include_text=True)
        except Exception as e:
            log.error(f"Parse failed for {pdf_blob}: {e}")
            stats["exceptions"].append({"blob": pdf_blob, "error": f"parse: {e}"})
            stats["upload_errors"] += 1
            continue

        # Check if text was extracted
        raw_text = parser_output.get("text", "")
        if len(raw_text.strip()) < 50:
            stats["terminal_no_text"] += 1
            stats["exceptions"].append({
                "blob": pdf_blob, "error": "terminal_no_text",
                "text_length": len(raw_text),
            })
            continue

        # 3. Read scraper metadata JSON and merge
        meta_blob_path = _doc_id_to_meta_blob(doc_id)
        try:
            meta_bytes = raw_container.get_blob_client(meta_blob_path).download_blob().readall()
            scraper_meta = json.loads(meta_bytes)
            norm = _normalize_scraper_fields(scraper_meta)
            parser_output = merge_with_scraper_metadata(parser_output, norm)
        except Exception:
            pass  # metadata optional, continue without it

        # 4. Override tribunal fields from config
        parser_output["tribunal_type"] = "TCE"
        parser_output["uf"] = cfg.uf
        detected = parser_output.get("tribunal_name", "").upper()
        if not detected.startswith("TRIBUNAL DE CONTAS DO ESTADO") and \
           not detected.startswith(f"TCE-{cfg.uf}"):
            parser_output["tribunal_name"] = cfg.display_name

        # 5. Transform to kb-legal
        try:
            kb_doc = transform_parser_to_kblegal(
                parser_output, pdf_blob, config=cfg,
            )
        except Exception as e:
            log.error(f"Mapping failed for {pdf_blob}: {e}")
            stats["exceptions"].append({"blob": pdf_blob, "error": f"mapping: {e}"})
            stats["upload_errors"] += 1
            continue

        if not kb_doc:
            stats["skipped_no_content"] += 1
            continue

        # 6. Validate
        errors = validate_kblegal_doc(kb_doc)
        if errors:
            log.warning(f"Validation errors for {pdf_blob}: {errors}")
            stats["validation_errors"] += 1
            stats["exceptions"].append({
                "blob": pdf_blob, "error": f"validation: {errors}",
            })

        # 7. Build envelope
        envelope = {
            "kb_doc": kb_doc,
            "metadata": {
                "blob_path": pdf_blob,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "parser_version": "tce_parser_v3",
                "mapping_version": "mapping_tce_to_kblegal_v1",
                "source_mode": "batch_from_raw_pdfs",
                "tribunal_id": TRIBUNAL_ID,
            },
            "parser_raw": {
                k: v for k, v in parser_output.items()
                if k not in ("text", "text_1")
            },
        }

        # 8. Upload (or dry-run)
        if dry_run:
            log.info(f"[DRY-RUN] Would write kb-raw/{kb_key}")
            log.info(f"  title: {kb_doc.get('title')}")
            log.info(f"  content len: {len(kb_doc.get('content', ''))}")
            log.info(f"  fields: {len(kb_doc)}/19")
            log.info(f"  validation: {'PASS' if not errors else errors}")
            stats["parsed"] += 1
        else:
            try:
                kb_container.get_blob_client(kb_key).upload_blob(
                    json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8"),
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type="application/json; charset=utf-8"
                    ),
                )
                stats["parsed"] += 1
            except Exception as e:
                log.error(f"Upload failed for {kb_key}: {e}")
                stats["upload_errors"] += 1
                stats["exceptions"].append({
                    "blob": pdf_blob, "error": f"upload: {e}",
                })

        if (i + 1) % LOG_INTERVAL == 0:
            _log_progress(i + 1, stats, start_time)

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 1)
    stats["rate_per_min"] = round(stats["parsed"] / (elapsed / 60), 1) if elapsed > 0 else 0

    # --- Final report ---
    log.info("=" * 60)
    log.info(f"COMPLETE: {TRIBUNAL_ID}")
    log.info(f"  Total source PDFs:    {stats['total']:,}")
    log.info(f"  Parsed & uploaded:    {stats['parsed']:,}")
    log.info(f"  Skipped (existing):   {stats['skipped_existing']:,}")
    log.info(f"  Terminal (no text):   {stats['terminal_no_text']:,}")
    log.info(f"  Skipped (no content): {stats['skipped_no_content']:,}")
    log.info(f"  Validation errors:    {stats['validation_errors']:,}")
    log.info(f"  Upload errors:        {stats['upload_errors']:,}")
    log.info(f"  Elapsed: {elapsed:.1f}s ({stats['rate_per_min']}/min)")
    log.info("=" * 60)

    # Checksum
    accounted = (
        stats["parsed"]
        + stats["skipped_existing"]
        + stats["terminal_no_text"]
        + stats["skipped_no_content"]
        + stats["upload_errors"]
    )
    if accounted != stats["total"]:
        log.warning(f"CHECKSUM MISMATCH: accounted={accounted} != total={stats['total']}")
    else:
        log.info(f"CHECKSUM OK: {accounted} == {stats['total']}")

    # Save report
    report = {
        "kind": "parse_batch_report",
        "tribunal_id": TRIBUNAL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "stats": {k: v for k, v in stats.items() if k != "exceptions"},
        "exception_count": len(stats["exceptions"]),
        "exceptions_sample": stats["exceptions"][:50],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"parse_tce_rs_{'dryrun' if dry_run else 'batch'}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log.info(f"Report saved to {report_path}")

    # Save exceptions to kb-raw
    if not dry_run and stats["exceptions"]:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            exc_key = f"{EXCEPTION_PREFIX}tce-rs_{ts}.json"
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
        f"(parsed={stats['parsed']:,} skip={stats['skipped_existing']:,} "
        f"no_text={stats['terminal_no_text']:,} err={stats['upload_errors']:,}) "
        f"{rate:.0f}/min"
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

AUDIT_CHECKS = [
    ("tribunal", lambda d: d.get("kb_doc", {}).get("tribunal") == "TCE"),
    ("uf", lambda d: d.get("kb_doc", {}).get("uf") == "RS"),
    ("authority_score", lambda d: d.get("kb_doc", {}).get("authority_score") == 0.80),
    ("region", lambda d: d.get("kb_doc", {}).get("region") == "SUL"),
    ("parser_version", lambda d: d.get("metadata", {}).get("parser_version") == "tce_parser_v3"),
    ("content_len_gt_50", lambda d: len(d.get("kb_doc", {}).get("content", "")) > 50),
    ("chunk_id_present", lambda d: bool(d.get("kb_doc", {}).get("chunk_id"))),
    ("doc_type", lambda d: d.get("kb_doc", {}).get("doc_type") == "jurisprudencia"),
    ("blob_path_present", lambda d: bool(d.get("metadata", {}).get("blob_path"))),
    ("processed_at_present", lambda d: bool(d.get("metadata", {}).get("processed_at"))),
    ("citation_present", lambda d: bool(d.get("kb_doc", {}).get("citation"))),
    ("year_present", lambda d: d.get("kb_doc", {}).get("year") is not None),
    ("title_present", lambda d: bool(d.get("kb_doc", {}).get("title"))),
]


def run_audit() -> dict:
    parsed_conn = _get_conn_string("GOVY_STORAGE_CONNECTION", PARSED_ACCOUNT)
    parsed_service = BlobServiceClient.from_connection_string(parsed_conn)
    kb_container = parsed_service.get_container_client(KB_RAW_CONTAINER)

    log.info(f"Listing blobs in {KB_RAW_CONTAINER}/{PARSED_PREFIX} for audit...")
    all_blobs = []
    for blob in kb_container.list_blobs(name_starts_with=PARSED_PREFIX):
        if blob.name.endswith(".json"):
            all_blobs.append(blob.name)
    log.info(f"Found {len(all_blobs):,} kb-raw blobs for TCE-RS")

    if not all_blobs:
        log.error("No blobs found for audit!")
        return {"error": "no_blobs"}

    # --- Sampling: 15 random + 15 stratified ---
    rng = random.Random(42)
    sample_names = set()

    random_pool = list(all_blobs)
    rng.shuffle(random_pool)
    for name in random_pool[:15]:
        sample_names.add(name)

    sorted_blobs = sorted(all_blobs)
    n = len(sorted_blobs)
    for name in sorted_blobs[:5]:
        sample_names.add(name)
    mid = n // 2
    for name in sorted_blobs[max(0, mid - 2):mid + 3]:
        sample_names.add(name)
    for name in sorted_blobs[-5:]:
        sample_names.add(name)

    sample_list = list(sample_names)[:30]
    log.info(f"Auditing {len(sample_list)} samples...")

    results = []
    pass_count = 0
    fail_count = 0

    for blob_name in sample_list:
        try:
            blob_data = kb_container.get_blob_client(blob_name).download_blob().readall()
            envelope = json.loads(blob_data)
        except Exception as e:
            results.append({
                "blob": blob_name, "status": "ERROR",
                "error": str(e), "checks": {},
            })
            fail_count += 1
            continue

        checks = {}
        all_pass = True
        for check_name, check_fn in AUDIT_CHECKS:
            try:
                passed = check_fn(envelope)
            except Exception:
                passed = False
            checks[check_name] = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False

        status = "PASS" if all_pass else "FAIL"
        if all_pass:
            pass_count += 1
        else:
            fail_count += 1

        results.append({
            "blob": blob_name, "status": status, "checks": checks,
        })

    audit = {
        "kind": "audit_report",
        "tribunal_id": TRIBUNAL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_kb_raw_blobs": len(all_blobs),
        "samples_audited": len(sample_list),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "verdict": "PASS" if fail_count == 0 else "FAIL",
        "results": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    audit_path = REPORT_DIR / f"audit_tce_rs_{ts}.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    log.info(f"Audit saved to {audit_path}")

    try:
        audit_blob_key = f"{REPORT_BLOB_PREFIX}tce-rs_audit_{ts}.json"
        kb_container.get_blob_client(audit_blob_key).upload_blob(
            json.dumps(audit, ensure_ascii=False, indent=2).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(
                content_type="application/json; charset=utf-8"
            ),
        )
        log.info(f"Audit uploaded to kb-raw/{audit_blob_key}")
    except Exception as e:
        log.warning(f"Could not upload audit to blob: {e}")

    log.info(f"AUDIT VERDICT: {audit['verdict']} ({pass_count}/{len(sample_list)} PASS)")
    return audit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch parser TCE-RS: juris-raw PDFs -> kb-raw"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    if args.audit_only:
        audit = run_audit()
        sys.exit(0 if audit.get("verdict") == "PASS" else 1)

    stats = run(
        dry_run=args.dry_run,
        limit=args.limit,
        skip_existing=not args.no_skip_existing,
    )

    if stats["upload_errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
