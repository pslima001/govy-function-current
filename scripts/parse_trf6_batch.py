#!/usr/bin/env python3
"""
parse_trf6_batch.py — Batch parser para TRF6 (1.524 docs -> kb-raw)

Le blobs metadata.json de juris-raw/trf6/acordaos/{doc_id}/metadata.json
(sttcejurisprudencia), parseia com trf6_parser, transforma via
mapping_tce_to_kblegal, e grava envelopes JSON em kb-raw/trf6/
(stgovyparsetestsponsor).

Estrutura TRF6: 2 blobs/doc (metadata.json + inteiro_teor.html)
O campo full_text ja vem extraido pelo scraper no metadata.json.

Usage:
  python scripts/parse_trf6_batch.py --dry-run --limit 5
  python scripts/parse_trf6_batch.py
  python scripts/parse_trf6_batch.py --audit-only

Environment:
  TCE_STORAGE_CONNECTION    — conn string para sttcejurisprudencia
  GOVY_STORAGE_CONNECTION   — conn string para stgovyparsetestsponsor
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from azure.storage.blob import BlobServiceClient, ContentSettings

from govy.api.mapping_tce_to_kblegal import (
    transform_parser_to_kblegal,
    validate_kblegal_doc,
)
from govy.api.trf6_parser import parse_trf6_json
from govy.config.tribunal_registry import get_config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("parse-trf6")

for noisy in ("azure.core.pipeline.policies", "azure.storage", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRIBUNAL_ID = "trf6"
RAW_ACCOUNT = "sttcejurisprudencia"
RAW_CONTAINER = "juris-raw"
RAW_PREFIX = "trf6/acordaos/"

PARSED_ACCOUNT = "stgovyparsetestsponsor"
KB_RAW_CONTAINER = "kb-raw"
PARSED_PREFIX = "trf6/"

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


def _metadata_blob_to_doc_id(blob_name: str) -> str:
    """
    Converte path do metadata.json para doc_id.
    Ex: trf6/acordaos/trf6--000000849201440138066--3817453221249550/metadata.json
        -> trf6--000000849201440138066--3817453221249550
    """
    # Remove prefix and /metadata.json
    parts = blob_name.replace(RAW_PREFIX, "").split("/")
    return parts[0] if parts else ""


def _doc_id_to_kb_key(doc_id: str) -> str:
    return f"{PARSED_PREFIX}{doc_id}.json"


# ---------------------------------------------------------------------------
# Main parse logic
# ---------------------------------------------------------------------------

def run(
    dry_run: bool = False,
    limit: int = 0,
    skip_existing: bool = True,
) -> dict:
    cfg = get_config(TRIBUNAL_ID)

    raw_conn = _get_conn_string("TCE_STORAGE_CONNECTION", RAW_ACCOUNT)
    raw_service = BlobServiceClient.from_connection_string(raw_conn)
    raw_container = raw_service.get_container_client(RAW_CONTAINER)

    if not dry_run:
        parsed_conn = _get_conn_string("GOVY_STORAGE_CONNECTION", PARSED_ACCOUNT)
        parsed_service = BlobServiceClient.from_connection_string(parsed_conn)
        kb_container = parsed_service.get_container_client(KB_RAW_CONTAINER)
    else:
        kb_container = None

    # --- List source blobs (only metadata.json) ---
    log.info(f"Listing metadata.json blobs in {RAW_CONTAINER}/{RAW_PREFIX}...")
    source_blobs = []
    for blob in raw_container.list_blobs(name_starts_with=RAW_PREFIX):
        if blob.name.endswith("metadata.json"):
            source_blobs.append(blob.name)
    log.info(f"Found {len(source_blobs):,} metadata.json files ({len(source_blobs)} docs)")

    # --- List existing kb-raw blobs ---
    existing_keys = set()
    if skip_existing and not dry_run:
        log.info(f"Listing existing blobs in {KB_RAW_CONTAINER}/{PARSED_PREFIX}...")
        for blob in kb_container.list_blobs(name_starts_with=PARSED_PREFIX):
            existing_keys.add(blob.name)
        log.info(f"Found {len(existing_keys):,} existing kb-raw blobs")

    if limit > 0:
        source_blobs = source_blobs[:limit]
        log.info(f"Limited to {len(source_blobs)} items")

    # --- Process ---
    stats = {
        "total": len(source_blobs),
        "parsed": 0,
        "skipped_existing": 0,
        "terminal_no_text": 0,
        "skipped_no_content": 0,
        "validation_errors": 0,
        "upload_errors": 0,
        "exceptions": [],
    }
    samples = []
    start_time = time.time()

    for i, blob_name in enumerate(source_blobs):
        doc_id = _metadata_blob_to_doc_id(blob_name)
        kb_key = _doc_id_to_kb_key(doc_id)

        if skip_existing and kb_key in existing_keys:
            stats["skipped_existing"] += 1
            if (i + 1) % LOG_INTERVAL == 0:
                _log_progress(i + 1, stats, start_time)
            continue

        # 1. Download metadata.json
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
            parser_output = parse_trf6_json(data)
        except Exception as e:
            log.error(f"Parse failed for {blob_name}: {e}")
            stats["exceptions"].append({"blob": blob_name, "error": f"parse: {e}"})
            stats["upload_errors"] += 1
            continue

        if parser_output is None:
            stats["terminal_no_text"] += 1
            stats["exceptions"].append({
                "blob": blob_name,
                "error": "terminal_no_text",
            })
            continue

        # 3. Transform
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

        # 5. Build envelope
        envelope = {
            "kb_doc": kb_doc,
            "metadata": {
                "blob_path": blob_name,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "parser_version": "trf6_json_inline_v1",
                "mapping_version": "mapping_tce_to_kblegal_v1",
                "source_mode": "batch_from_raw_jsons",
            },
            "parser_raw": {
                k: v for k, v in parser_output.items()
                if k not in ("text", "text_1")
            },
        }

        # 6. Upload
        if dry_run:
            log.info(f"[DRY-RUN] Would write kb-raw/{kb_key}")
            log.info(f"  chunk_id: {kb_doc.get('chunk_id')}")
            log.info(f"  title: {kb_doc.get('title')}")
            log.info(f"  content len: {len(kb_doc.get('content', ''))}")
            log.info(f"  fields: {len(kb_doc)}/19")
            log.info(f"  validation: {'PASS' if not errors else errors}")
            stats["parsed"] += 1
            if len(samples) < 5:
                samples.append({"kb_key": kb_key, "kb_doc": kb_doc})
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
                    "blob": blob_name, "error": f"upload: {e}",
                })

        if (i + 1) % LOG_INTERVAL == 0:
            _log_progress(i + 1, stats, start_time)

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 1)
    stats["rate_per_min"] = round(stats["parsed"] / (elapsed / 60), 1) if elapsed > 0 else 0

    log.info("=" * 60)
    log.info(f"COMPLETE: {TRIBUNAL_ID}")
    log.info(f"  Total source blobs:   {stats['total']:,}")
    log.info(f"  Parsed & uploaded:    {stats['parsed']:,}")
    log.info(f"  Skipped (existing):   {stats['skipped_existing']:,}")
    log.info(f"  Terminal (no text):   {stats['terminal_no_text']:,}")
    log.info(f"  Skipped (no content): {stats['skipped_no_content']:,}")
    log.info(f"  Validation errors:    {stats['validation_errors']:,}")
    log.info(f"  Upload errors:        {stats['upload_errors']:,}")
    log.info(f"  Elapsed: {elapsed:.1f}s ({stats['rate_per_min']}/min)")
    log.info("=" * 60)

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
    report_path = REPORT_DIR / f"parse_trf6_{'dryrun' if dry_run else 'batch'}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log.info(f"Report saved to {report_path}")

    if not dry_run and stats["exceptions"]:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            exc_key = f"{EXCEPTION_PREFIX}trf6_{ts}.json"
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
        f"no_text={stats['terminal_no_text']:,} err={stats['upload_errors']:,}) "
        f"{rate:.0f}/min"
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

AUDIT_CHECKS = [
    ("tribunal", lambda d: d.get("kb_doc", {}).get("tribunal") == "TRF6"),
    ("authority_score", lambda d: d.get("kb_doc", {}).get("authority_score") == 0.85),
    ("region", lambda d: d.get("kb_doc", {}).get("region") == "SUDESTE"),
    ("parser_version", lambda d: d.get("metadata", {}).get("parser_version") == "trf6_json_inline_v1"),
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
    log.info(f"Found {len(all_blobs):,} kb-raw blobs for TRF6")

    if len(all_blobs) == 0:
        log.error("No blobs found for audit!")
        return {"error": "no_blobs"}

    rng = random.Random(42)
    sample_names = set()

    random_pool = list(all_blobs)
    rng.shuffle(random_pool)
    for name in random_pool:
        if len(sample_names) >= 15:
            break
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
    audit_path = REPORT_DIR / f"audit_trf6_{ts}.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    log.info(f"Audit saved to {audit_path}")

    try:
        audit_blob_key = f"{REPORT_BLOB_PREFIX}trf6_audit_{ts}.json"
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
# REPORT_FINAL
# ---------------------------------------------------------------------------

def generate_report_final(stats: dict, audit: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# REPORT_FINAL — TRF6 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF6 — Tribunal Regional Federal da 6\u00aa Regi\u00e3o |
| Parser | trf6_json_inline_v1 |
| Source | juris-raw/trf6/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/trf6/ (stgovyparsetestsponsor) |
| Generated | {ts} |

## Inventory

| Metric | Count |
|--------|-------|
| Source docs (metadata.json) | {stats.get('total', 'N/A'):,} |
| Parsed & uploaded | {stats.get('parsed', 'N/A'):,} |
| Skipped (existing) | {stats.get('skipped_existing', 'N/A'):,} |
| Terminal (no text) | {stats.get('terminal_no_text', 'N/A'):,} |
| Skipped (no content) | {stats.get('skipped_no_content', 'N/A'):,} |
| Validation errors | {stats.get('validation_errors', 'N/A'):,} |
| Upload errors | {stats.get('upload_errors', 'N/A'):,} |
| Elapsed | {stats.get('elapsed_seconds', 'N/A')}s |
| Rate | {stats.get('rate_per_min', 'N/A')}/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | {audit.get('samples_audited', 'N/A')} |
| PASS | {audit.get('pass_count', 'N/A')} |
| FAIL | {audit.get('fail_count', 'N/A')} |
| Verdict | **{audit.get('verdict', 'N/A')}** |

## Checksum

parsed + terminal_no_text + skipped_no_content + skipped_existing + upload_errors = total

{stats.get('parsed', 0)} + {stats.get('terminal_no_text', 0)} + {stats.get('skipped_no_content', 0)} + {stats.get('skipped_existing', 0)} + {stats.get('upload_errors', 0)} = {stats.get('total', 0)}
"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "REPORT_FINAL_trf6.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    log.info(f"REPORT_FINAL saved to {report_path}")

    try:
        parsed_conn = _get_conn_string("GOVY_STORAGE_CONNECTION", PARSED_ACCOUNT)
        parsed_service = BlobServiceClient.from_connection_string(parsed_conn)
        kb_container = parsed_service.get_container_client(KB_RAW_CONTAINER)
        report_blob_key = f"{REPORT_BLOB_PREFIX}REPORT_FINAL_trf6.md"
        kb_container.get_blob_client(report_blob_key).upload_blob(
            md.encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(
                content_type="text/markdown; charset=utf-8"
            ),
        )
        log.info(f"REPORT_FINAL uploaded to kb-raw/{report_blob_key}")
    except Exception as e:
        log.warning(f"Could not upload REPORT_FINAL to blob: {e}")

    return md


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch parser TRF6: juris-raw JSONs -> kb-raw"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    if args.audit_only:
        audit = run_audit()
        batch_report_path = REPORT_DIR / "parse_trf6_batch.json"
        if batch_report_path.exists():
            with open(batch_report_path, "r", encoding="utf-8") as f:
                batch_report = json.load(f)
            stats = batch_report.get("stats", {})
        else:
            stats = {}
        generate_report_final(stats, audit)
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
