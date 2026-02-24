#!/usr/bin/env python3
"""
batch_index_kb.py - Batch index kb-raw JSONs into Azure AI Search (kb-legal index)

Reads kb-raw blobs from stgovyparsetestsponsor, extracts kb_doc,
normalizes data, and POSTs batches to /api/kb/index/upsert.

Usage:
  python batch_index_kb.py --tribunal-id tce-mg [--batch-size 10] [--dry-run]

Environment variables:
  GOVY_FUNC_BASE    - Function App base URL (default: https://func-govy-parse-test.azurewebsites.net)
  GOVY_FUNC_KEY     - Function App key for authentication
  GOVY_STORAGE_CONN - Connection string for stgovyparsetestsponsor (kb-raw reader)

Resume: progress is saved to outputs/batch_index_{tribunal_id}_progress.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests
from azure.storage.blob import BlobServiceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("batch_index_kb")

# Suppress verbose Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ======================================================================
# CONFIG
# ======================================================================

FUNC_BASE = os.environ.get(
    "GOVY_FUNC_BASE",
    "https://func-govy-parse-test.azurewebsites.net",
)
FUNC_KEY = os.environ.get("GOVY_FUNC_KEY", "")
STORAGE_CONN = os.environ.get("GOVY_STORAGE_CONN", "")

KB_RAW_CONTAINER = "kb-raw"
UPSERT_PATH = "/api/kb/index/upsert"

# Tribunal → forced values (to fix parser misidentifications)
TRIBUNAL_OVERRIDES = {
    "tce-mg": {"tribunal": "TCE", "uf": "MG"},
    "tce-sp": {"tribunal": "TCE", "uf": "SP"},
    "tce-sc": {"tribunal": "TCE", "uf": "SC"},
    "tce-rs": {"tribunal": "TCE", "uf": "RS"},
    "tce-pb": {"tribunal": "TCE", "uf": "PB"},
}


# ======================================================================
# HELPERS
# ======================================================================


def progress_file(tribunal_id: str) -> str:
    os.makedirs("outputs", exist_ok=True)
    return f"outputs/batch_index_{tribunal_id}_progress.json"


def load_progress(tribunal_id: str) -> dict:
    path = progress_file(tribunal_id)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"last_batch": -1, "indexed": 0, "failed": 0, "skipped": 0, "errors": []}


def save_progress(tribunal_id: str, progress: dict):
    path = progress_file(tribunal_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def normalize_kb_doc(kb_doc: dict, tribunal_id: str) -> dict:
    """Apply forced overrides and defaults for known data issues."""
    doc = dict(kb_doc)

    # Force tribunal/uf for known tribunal IDs (parser sometimes misidentifies)
    overrides = TRIBUNAL_OVERRIDES.get(tribunal_id, {})
    for key, val in overrides.items():
        doc[key] = val

    # Default effect to NAO_CLARO if missing (required for jurisprudencia)
    if not doc.get("effect"):
        doc["effect"] = "NAO_CLARO"

    # Ensure doc_type is set
    if not doc.get("doc_type"):
        doc["doc_type"] = "jurisprudencia"

    return doc


def post_upsert(chunks: list, generate_embeddings: bool = True) -> dict:
    """POST chunks to the upsert endpoint. Returns response dict."""
    url = f"{FUNC_BASE}{UPSERT_PATH}?code={FUNC_KEY}"
    payload = {
        "chunks": chunks,
        "generate_embeddings": generate_embeddings,
    }

    resp = requests.post(url, json=payload, timeout=300)

    if resp.status_code >= 500:
        return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}

    try:
        return resp.json()
    except Exception:
        return {"status": "error", "error": f"Invalid JSON response: {resp.text[:500]}"}


# ======================================================================
# MAIN
# ======================================================================


def main():
    parser = argparse.ArgumentParser(description="Batch index kb-raw into Azure AI Search")
    parser.add_argument("--tribunal-id", required=True, help="e.g. tce-mg, tce-sp")
    parser.add_argument("--batch-size", type=int, default=10, help="Chunks per upsert call (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="List blobs and validate, do not index")
    parser.add_argument("--reset", action="store_true", help="Reset progress and start from scratch")
    parser.add_argument("--limit", type=int, default=0, help="Max blobs to process (0=all)")
    parser.add_argument("--no-embeddings", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()

    tribunal_id = args.tribunal_id
    batch_size = args.batch_size
    prefix = f"{tribunal_id.replace('-', '-')}--"  # e.g. tce-mg--

    # Validate config
    if not FUNC_KEY:
        log.error("GOVY_FUNC_KEY not set")
        sys.exit(1)
    if not STORAGE_CONN:
        log.error("GOVY_STORAGE_CONN not set")
        sys.exit(1)

    # Load progress
    if args.reset:
        progress = {"last_batch": -1, "indexed": 0, "failed": 0, "skipped": 0, "errors": []}
        save_progress(tribunal_id, progress)
    else:
        progress = load_progress(tribunal_id)

    log.info(f"=== Batch Index KB: {tribunal_id} ===")
    log.info(f"Endpoint: {FUNC_BASE}{UPSERT_PATH}")
    log.info(f"Batch size: {batch_size}")
    log.info(f"Resume from batch: {progress['last_batch'] + 1}")

    # 1. List all kb-raw blobs
    log.info(f"Listing blobs with prefix '{prefix}' in {KB_RAW_CONTAINER}...")
    blob_service = BlobServiceClient.from_connection_string(STORAGE_CONN)
    container = blob_service.get_container_client(KB_RAW_CONTAINER)

    blob_names = []
    for blob in container.list_blobs(name_starts_with=prefix):
        if blob.name.endswith(".json"):
            blob_names.append(blob.name)
    blob_names.sort()

    total_blobs = len(blob_names)
    log.info(f"Found {total_blobs} JSON blobs")

    if args.limit > 0:
        blob_names = blob_names[: args.limit]
        log.info(f"Limited to {len(blob_names)} blobs")

    if total_blobs == 0:
        log.warning("No blobs found. Check prefix and container.")
        return

    # 2. Process in batches
    total_batches = (len(blob_names) + batch_size - 1) // batch_size
    start_batch = progress["last_batch"] + 1
    generate_emb = not args.no_embeddings

    log.info(f"Total batches: {total_batches}, starting from: {start_batch}")
    log.info(f"Generate embeddings: {generate_emb}")

    if args.dry_run:
        log.info("[DRY RUN] Would process the following:")
        # Validate a sample
        sample_size = min(5, len(blob_names))
        for name in blob_names[:sample_size]:
            data = json.loads(container.get_blob_client(name).download_blob().readall())
            kb_doc = data.get("kb_doc", {})
            kb_doc = normalize_kb_doc(kb_doc, tribunal_id)
            log.info(
                f"  {name}: chunk_id={kb_doc.get('chunk_id', '?')[:20]}... "
                f"tribunal={kb_doc.get('tribunal')} uf={kb_doc.get('uf')} "
                f"effect={kb_doc.get('effect')} secao={kb_doc.get('secao')} "
                f"content_len={len(kb_doc.get('content', ''))}"
            )
        log.info(f"[DRY RUN] Total: {total_blobs} blobs in {total_batches} batches")
        return

    t_start = time.time()

    for batch_idx in range(start_batch, total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(blob_names))
        batch_names = blob_names[batch_start:batch_end]

        # Download and extract kb_doc
        chunks = []
        batch_skipped = 0
        for name in batch_names:
            try:
                raw = container.get_blob_client(name).download_blob().readall()
                data = json.loads(raw)
                kb_doc = data.get("kb_doc", {})

                if not kb_doc or not kb_doc.get("content"):
                    batch_skipped += 1
                    continue

                kb_doc = normalize_kb_doc(kb_doc, tribunal_id)
                chunks.append(kb_doc)
            except Exception as e:
                log.warning(f"  Error reading {name}: {e}")
                progress["errors"].append({"blob": name, "error": str(e), "phase": "download"})

        if not chunks:
            log.info(f"Batch {batch_idx + 1}/{total_batches}: no valid chunks (skipped={batch_skipped})")
            progress["last_batch"] = batch_idx
            progress["skipped"] += batch_skipped
            save_progress(tribunal_id, progress)
            continue

        # POST to upsert
        retries = 0
        max_retries = 3
        result = None

        while retries <= max_retries:
            try:
                result = post_upsert(chunks, generate_embeddings=generate_emb)
                if result.get("status") != "error":
                    break
                log.warning(f"  Upsert error (attempt {retries + 1}): {result.get('error', result.get('errors', []))}")
            except requests.exceptions.Timeout:
                log.warning(f"  Timeout on batch {batch_idx + 1} (attempt {retries + 1})")
                result = {"status": "error", "error": "timeout", "indexed": 0, "failed": len(chunks)}
            except Exception as e:
                log.warning(f"  Request error (attempt {retries + 1}): {e}")
                result = {"status": "error", "error": str(e), "indexed": 0, "failed": len(chunks)}

            retries += 1
            if retries <= max_retries:
                wait = 5 * retries
                log.info(f"  Retrying in {wait}s...")
                time.sleep(wait)

        indexed = result.get("indexed", 0)
        failed = result.get("failed", 0)
        val_errors = result.get("validation_errors", [])

        progress["indexed"] += indexed
        progress["failed"] += failed
        progress["skipped"] += batch_skipped
        progress["last_batch"] = batch_idx

        if val_errors:
            for ve in val_errors[:3]:
                progress["errors"].append({"batch": batch_idx, "validation": ve})

        save_progress(tribunal_id, progress)

        elapsed = time.time() - t_start
        rate = progress["indexed"] / elapsed if elapsed > 0 else 0
        eta_s = (total_blobs - (batch_end)) / rate if rate > 0 else 0
        eta_min = eta_s / 60

        status_icon = "OK" if result.get("status") == "success" else result.get("status", "?")
        log.info(
            f"Batch {batch_idx + 1}/{total_batches} [{status_icon}]: "
            f"indexed={indexed} failed={failed} | "
            f"Total: {progress['indexed']}/{total_blobs} "
            f"({progress['indexed']*100/total_blobs:.1f}%) "
            f"ETA: {eta_min:.0f}min"
        )

        # Rate limit: small delay between batches
        time.sleep(0.5)

    # 3. Final report
    elapsed_total = time.time() - t_start
    log.info("=" * 60)
    log.info(f"BATCH INDEX COMPLETE: {tribunal_id}")
    log.info(f"  Total blobs:  {total_blobs}")
    log.info(f"  Indexed:      {progress['indexed']}")
    log.info(f"  Failed:       {progress['failed']}")
    log.info(f"  Skipped:      {progress['skipped']}")
    log.info(f"  Errors:       {len(progress['errors'])}")
    log.info(f"  Elapsed:      {elapsed_total/60:.1f} min")
    log.info(f"  Progress:     {progress_file(tribunal_id)}")
    log.info("=" * 60)

    # Save final report
    report_path = f"outputs/batch_index_{tribunal_id}_report.json"
    report = {
        "tribunal_id": tribunal_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_blobs": total_blobs,
        "indexed": progress["indexed"],
        "failed": progress["failed"],
        "skipped": progress["skipped"],
        "errors_count": len(progress["errors"]),
        "elapsed_seconds": round(elapsed_total, 1),
        "first_errors": progress["errors"][:20],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log.info(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
