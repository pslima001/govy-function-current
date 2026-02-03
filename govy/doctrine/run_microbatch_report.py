"""
run_microbatch_report.py - Micro-batch com relatorio de qualidade.
Processa 10-20 arquivos e gera report JSON com stats e argument_role counts.
"""
from __future__ import annotations
import json
import os
import logging
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

logger = logging.getLogger(__name__)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING nao definida.")
    container_source = os.environ.get("DOCTRINE_CONTAINER_SOURCE", "doutrina")
    container_processed = os.environ.get("DOCTRINE_CONTAINER_PROCESSED", "doutrina-processed")
    force = os.environ.get("DOCTRINE_FORCE_REPROCESS", "false").lower() == "true"
    manifest_path = os.environ.get("DOCTRINE_MICROBATCH_MANIFEST_JSON", "")
    report_path = os.environ.get("DOCTRINE_MICROBATCH_REPORT_PATH", "outputs/microbatch_report_doctrine_v2.json")

    blob_service = BlobServiceClient.from_connection_string(conn)

    # Determinar arquivos
    if manifest_path and os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        defaults = manifest.get("default", {})
        files_config = manifest.get("files", {})
        if files_config:
            file_list = list(files_config.keys())
        else:
            file_list = _list_blobs(blob_service, container_source, limit=20)
    else:
        defaults = {"etapa_processo": "habilitacao", "tema_principal": "habilitacao"}
        files_config = {}
        file_list = _list_blobs(blob_service, container_source, limit=20)

    logger.info(f"Micro-batch: {len(file_list)} arquivos para processar")

    results = []
    for blob_name in file_list:
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
            logger.info(f"  OK: {blob_name} -> {result.get('status')}")
        except Exception as e:
            results.append({"blob_name": blob_name, "result": {"status": "failed", "error": str(e)}})
            logger.error(f"  FALHOU: {blob_name} -> {e}")

    # Gerar report
    report = _build_report(results)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Report salvo em: {report_path}")
    logger.info(f"Resumo: processed={report['summary']['processed']} failed={report['summary']['failed']}")

def _list_blobs(blob_service, container_name, limit=20):
    container = blob_service.get_container_client(container_name)
    blobs = []
    for b in container.list_blobs(name_starts_with="raw/"):
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
    role_counts = {}
    top_incertos = []
    for r in results:
        stats = r["result"].get("stats", {})
        for k in totals:
@'
"""
run_microbatch_report.py - Micro-batch com relatorio de qualidade.
Processa 10-20 arquivos e gera report JSON com stats e argument_role counts.
"""
from __future__ import annotations
import json
import os
import logging
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

logger = logging.getLogger(__name__)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING nao definida.")
    container_source = os.environ.get("DOCTRINE_CONTAINER_SOURCE", "doutrina")
    container_processed = os.environ.get("DOCTRINE_CONTAINER_PROCESSED", "doutrina-processed")
    force = os.environ.get("DOCTRINE_FORCE_REPROCESS", "false").lower() == "true"
    manifest_path = os.environ.get("DOCTRINE_MICROBATCH_MANIFEST_JSON", "")
    report_path = os.environ.get("DOCTRINE_MICROBATCH_REPORT_PATH", "outputs/microbatch_report_doctrine_v2.json")

    blob_service = BlobServiceClient.from_connection_string(conn)

    # Determinar arquivos
    if manifest_path and os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        defaults = manifest.get("default", {})
        files_config = manifest.get("files", {})
        if files_config:
            file_list = list(files_config.keys())
        else:
            file_list = _list_blobs(blob_service, container_source, limit=20)
    else:
        defaults = {"etapa_processo": "habilitacao", "tema_principal": "habilitacao"}
        files_config = {}
        file_list = _list_blobs(blob_service, container_source, limit=20)

    logger.info(f"Micro-batch: {len(file_list)} arquivos para processar")

    results = []
    for blob_name in file_list:
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
            logger.info(f"  OK: {blob_name} -> {result.get('status')}")
        except Exception as e:
            results.append({"blob_name": blob_name, "result": {"status": "failed", "error": str(e)}})
            logger.error(f"  FALHOU: {blob_name} -> {e}")

    # Gerar report
    report = _build_report(results)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Report salvo em: {report_path}")
    logger.info(f"Resumo: processed={report['summary']['processed']} failed={report['summary']['failed']}")

def _list_blobs(blob_service, container_name, limit=20):
    container = blob_service.get_container_client(container_name)
    blobs = []
    for b in container.list_blobs(name_starts_with="raw/"):
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
    role_counts = {}
    top_incertos = []
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
            "argument_role_counts": role_counts,
        },
        "top_incertos": top_incertos,
        "details": results,
    }

if __name__ == "__main__":
    main()
