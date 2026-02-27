"""run_microbatch_report.py - Micro-batch com relatorio de qualidade."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone

from govy.utils.azure_clients import get_blob_service_client
from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

logger = logging.getLogger(__name__)

# ── Guardrails defaults ───────────────────────────────────────────────────────
DEFAULT_MAX_DOCS = 50
DEFAULT_MAX_CHARS = 500_000


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _setup_logging(log_dir: str = "logs") -> None:
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"doctrine_microbatch_{stamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logger.info(f"Log file: {log_file}")


def _list_blobs(blob_service, container_name, limit=20):
    container = blob_service.get_container_client(container_name)
    blobs = []
    for b in container.list_blobs():
        if b.name.lower().endswith(".docx"):
            blobs.append(b.name)
            if len(blobs) >= limit:
                break
    return blobs


def _build_report(results):
    processed = sum(1 for r in results if r["result"].get("status") == "processed")
    already = sum(1 for r in results if r["result"].get("status") == "already_processed")
    failed = sum(1 for r in results if r["result"].get("status") == "failed")
    totals = {"raw_chunks": 0, "semantic_chunks": 0, "verbatim_legal_chunks": 0, "incertos": 0}
    for r in results:
        stats = r["result"].get("stats", {})
        for k in totals:
            totals[k] += stats.get(k, 0)
    return {
        "kind": "doctrine_v2_microbatch_report",
        "generated_at": _utc_now_iso(),
        "summary": {
            "total_files": len(results),
            "processed": processed,
            "already_processed": already,
            "failed": failed,
            "totals": totals,
        },
        "details": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Doctrine micro-batch with quality report")
    parser.add_argument("--max-docs", type=int, default=DEFAULT_MAX_DOCS, help=f"Max docs (default {DEFAULT_MAX_DOCS})")
    parser.add_argument(
        "--max-chars", type=int, default=DEFAULT_MAX_CHARS, help=f"Max total chars (default {DEFAULT_MAX_CHARS})"
    )
    args = parser.parse_args()

    _setup_logging()

    container_source = os.environ.get("DOCTRINE_CONTAINER_SOURCE", "kb-doutrina-raw")
    container_processed = os.environ.get("DOCTRINE_CONTAINER_PROCESSED", "kb-doutrina-processed")
    force = os.environ.get("DOCTRINE_FORCE_REPROCESS", "false").lower() == "true"
    manifest_path = os.environ.get("DOCTRINE_MICROBATCH_MANIFEST_JSON", "")
    report_path = os.environ.get("DOCTRINE_MICROBATCH_REPORT_PATH", "outputs/microbatch_report_doctrine_v2.json")
    blob_service = get_blob_service_client()
    if manifest_path and os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        defaults = manifest.get("default", {})
        files_config = manifest.get("files", {})
        file_list = list(files_config.keys()) if files_config else _list_blobs(blob_service, container_source)
    else:
        defaults = {"etapa_processo": "habilitacao", "tema_principal": "habilitacao"}
        files_config = {}
        file_list = _list_blobs(blob_service, container_source)

    # Guardrail: limit docs
    file_list = file_list[: args.max_docs]
    logger.info("Micro-batch: %d arquivos (max_docs=%d, max_chars=%d)", len(file_list), args.max_docs, args.max_chars)

    results = []
    total_chars = 0

    for blob_name in file_list:
        if total_chars >= args.max_chars:
            logger.warning(f"max_chars atingido ({total_chars}/{args.max_chars}), parando")
            break

        cfg = files_config.get(blob_name, defaults)
        req = DoctrineIngestRequest(
            blob_name=blob_name,
            etapa_processo=cfg.get("etapa_processo", defaults.get("etapa_processo", "habilitacao")),
            tema_principal=cfg.get("tema_principal", defaults.get("tema_principal", "habilitacao")),
            autor=cfg.get("autor", ""),
            obra=cfg.get("obra", ""),
            edicao=cfg.get("edicao", ""),
            ano=int(cfg.get("ano", 0) or 0),
            capitulo=cfg.get("capitulo", ""),
            secao=cfg.get("secao", ""),
            force_reprocess=force,
        )
        try:
            result = ingest_doctrine_process_once(blob_service, container_source, container_processed, req)
            results.append({"blob_name": blob_name, "result": result})
            total_chars += result.get("stats", {}).get("chars", 0)
            logger.info("  OK: %s -> %s", blob_name, result.get("status"))
        except Exception as e:
            results.append({"blob_name": blob_name, "result": {"status": "failed", "error": str(e)}})
            logger.error("  FALHOU: %s -> %s", blob_name, e)

    report = _build_report(results)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("Report salvo em: %s", report_path)


if __name__ == "__main__":
    main()
