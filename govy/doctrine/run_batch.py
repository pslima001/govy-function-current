from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from govy.utils.azure_clients import get_blob_service_client
from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

logger = logging.getLogger(__name__)

# ── Guardrails defaults ───────────────────────────────────────────────────────
DEFAULT_MAX_DOCS = 50
DEFAULT_MAX_WORKERS = 2
DEFAULT_MAX_CHARS = 500_000


def _load_manifest(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_meta(defaults: Dict[str, Any], file_meta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(defaults or {})
    out.update(file_meta or {})
    return out


def _setup_logging(log_dir: str = "logs") -> None:
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"doctrine_batch_{stamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logger.info(f"Log file: {log_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Doctrine batch processor")
    parser.add_argument(
        "--max-docs", type=int, default=DEFAULT_MAX_DOCS, help=f"Max docs to process (default {DEFAULT_MAX_DOCS})"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Max parallel workers (default {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--max-chars", type=int, default=DEFAULT_MAX_CHARS, help=f"Max total chars (default {DEFAULT_MAX_CHARS})"
    )
    args = parser.parse_args()

    _setup_logging()

    container_source = os.getenv("DOCTRINE_CONTAINER_SOURCE", "doutrina")
    container_processed = os.getenv("DOCTRINE_CONTAINER_PROCESSED", "doutrina-processed")
    manifest_path = os.getenv("DOCTRINE_MANIFEST_JSON", "")
    force_reprocess = os.getenv("DOCTRINE_FORCE_REPROCESS", "false").lower() == "true"
    blob_service = get_blob_service_client()
    manifest = _load_manifest(manifest_path)
    defaults = manifest.get("default", {})
    file_map = manifest.get("files", {})
    src_container = blob_service.get_container_client(container_source)
    blobs = [b.name for b in src_container.list_blobs() if b.name.lower().endswith(".docx")]

    # Guardrail: limit docs
    blobs = blobs[: args.max_docs]
    logger.info(f"Processing {len(blobs)} DOCX (max_docs={args.max_docs}, max_chars={args.max_chars})")

    ok = 0
    skipped = 0
    fail = 0
    total_chars = 0

    for blob_name in blobs:
        if total_chars >= args.max_chars:
            logger.warning(f"max_chars atingido ({total_chars}/{args.max_chars}), parando batch")
            break

        meta = _merge_meta(defaults, file_map.get(blob_name, {}))
        req = DoctrineIngestRequest(
            blob_name=blob_name,
            etapa_processo=str(meta.get("etapa_processo", "habilitacao")),
            tema_principal=str(meta.get("tema_principal", "habilitacao")),
            autor=str(meta.get("autor", "")),
            obra=str(meta.get("obra", "")),
            edicao=str(meta.get("edicao", "")),
            ano=int(meta.get("ano", 0) or 0),
            capitulo=str(meta.get("capitulo", "")),
            secao=str(meta.get("secao", "")),
            force_reprocess=force_reprocess,
        )
        try:
            res = ingest_doctrine_process_once(
                blob_service=blob_service,
                container_source=container_source,
                container_processed=container_processed,
                req=req,
            )
            if res.get("status") == "already_processed":
                skipped += 1
            else:
                ok += 1
                total_chars += res.get("stats", {}).get("chars", 0)
        except Exception as e:
            logger.error(f"Falha: {blob_name}: {e}")
            fail += 1

    logger.info(f"Batch finalizado. processed={ok} already_processed={skipped} failed={fail} total_chars={total_chars}")


if __name__ == "__main__":
    main()
