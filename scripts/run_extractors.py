#!/usr/bin/env python3
"""
Batch runner: executa relation_extractor + effective_date_extractor
contra todos os documentos do DB.

Fluxo:
  1. Lista todos os doc_ids do legal_document
  2. Para cada doc: baixa texto do blob → extrai relacoes + datas → grava no DB
  3. Gera relatorio JSON com resultados

Uso:
  python scripts/run_extractors.py [--limit N] [--doc-id X] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from govy.legal.relation_extractor import extract_relations, write_relations
from govy.legal.effective_date_extractor import extract_effective_dates, update_document_dates
from govy.legal.text_extractor import extract
from govy.legal.pipeline import _get_container, RAW_CONTAINER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_extractors")


def get_db_connection():
    import psycopg2
    connstr = os.environ.get(
        "POSTGRES_CONNSTR",
        "host=pg-govy-legal.postgres.database.azure.com port=5432 dbname=govy_legal user=govyadmin password=s39VebZSTag8I9VU6xHCN8w3zMgQ sslmode=require",
    )
    return psycopg2.connect(connstr)


def list_documents(conn, doc_id_filter=None, limit=0):
    """Lista documentos do DB com source_blob_path."""
    cur = conn.cursor()
    sql = "SELECT doc_id, source_blob_path, doc_type, char_count FROM legal_document"
    params = []
    if doc_id_filter:
        sql += " WHERE doc_id = %s"
        params.append(doc_id_filter)
    sql += " ORDER BY doc_id"
    if limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return [
        {"doc_id": r[0], "source_blob_path": r[1], "doc_type": r[2], "char_count": r[3]}
        for r in rows
    ]


def _get_blob_service():
    """Cria BlobServiceClient (connection string preferred for local)."""
    connstr = os.environ.get("AZURE_STORAGE_CONNSTR_SPONSOR", "")
    if connstr:
        from azure.storage.blob import BlobServiceClient
        return BlobServiceClient.from_connection_string(connstr)
    else:
        from govy.legal.pipeline import _get_container
        return None


_blob_svc = None


def download_text(blob_path: str) -> str:
    """Download blob e extrai texto."""
    global _blob_svc
    # blob_path format: normas-juridicas-raw/federal/BR/...
    parts = blob_path.split("/", 1)
    container_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else blob_path

    if _blob_svc is None:
        _blob_svc = _get_blob_service()

    if _blob_svc:
        container = _blob_svc.get_container_client(container_name)
    else:
        from govy.legal.pipeline import _get_container
        container = _get_container(container_name)

    blob_client = container.get_blob_client(blob_name)
    file_bytes = blob_client.download_blob().readall()
    filename = blob_name.split("/")[-1]
    result = extract(file_bytes, filename)
    return result.text


def run(args):
    conn = get_db_connection()
    docs = list_documents(conn, args.doc_id, args.limit)
    conn.close()

    total = len(docs)
    logger.info("=== %d documentos para processar ===", total)

    results = []
    total_relations = 0
    total_dates = 0
    errors = []
    t0 = time.time()

    for i, doc in enumerate(docs, 1):
        doc_id = doc["doc_id"]
        blob_path = doc["source_blob_path"]
        logger.info("[%d/%d] %s (%s chars)", i, total, doc_id, doc["char_count"])

        try:
            # Download and extract text
            text = download_text(blob_path)
            if not text or len(text) < 50:
                logger.warning("  Texto muito curto, pulando: %d chars", len(text) if text else 0)
                results.append({
                    "doc_id": doc_id,
                    "status": "skipped",
                    "reason": "texto curto",
                })
                continue

            # 1. Relations
            relations = extract_relations(text, doc_id)
            rel_high = sum(1 for r in relations if r.confidence == "high")
            rel_low = sum(1 for r in relations if r.confidence == "low")

            if not args.dry_run:
                write_relations(doc_id, relations)

            # 2. Effective dates
            dates = extract_effective_dates(text, doc_id)

            if not args.dry_run:
                update_document_dates(doc_id, dates)

            total_relations += len(relations)
            has_dates = dates.published_at is not None or dates.effective_from is not None
            if has_dates:
                total_dates += 1

            result = {
                "doc_id": doc_id,
                "doc_type": doc["doc_type"],
                "status": "ok" if not args.dry_run else "dry_run",
                "relations_total": len(relations),
                "relations_high": rel_high,
                "relations_low": rel_low,
                "relation_types": list(set(r.relation_type for r in relations)),
                "published_at": str(dates.published_at) if dates.published_at else None,
                "effective_from": str(dates.effective_from) if dates.effective_from else None,
                "status_vigencia": dates.status_vigencia,
                "vigor_pattern": dates.vigor_pattern,
            }

            # Log detail for relations
            if relations:
                for rel in relations:
                    logger.info(
                        "  REL: %s → %s [%s] confidence=%s",
                        rel.relation_type, rel.target_ref, rel.target_doc_id or "?", rel.confidence,
                    )

            if has_dates:
                logger.info(
                    "  DATE: published=%s, effective_from=%s, status=%s, pattern=%s",
                    dates.published_at, dates.effective_from, dates.status_vigencia, dates.vigor_pattern,
                )

            results.append(result)

        except Exception as e:
            logger.exception("  ERRO: %s", e)
            errors.append({"doc_id": doc_id, "error": str(e)})
            results.append({"doc_id": doc_id, "status": "error", "error": str(e)})

    elapsed = time.time() - t0

    # Summary
    ok = sum(1 for r in results if r.get("status") in ("ok", "dry_run"))
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    err = sum(1 for r in results if r.get("status") == "error")

    summary = {
        "total_docs": total,
        "ok": ok,
        "skipped": skipped,
        "errors": err,
        "total_relations": total_relations,
        "docs_with_dates": total_dates,
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": args.dry_run,
    }

    logger.info("=" * 60)
    logger.info("RESUMO: %d docs, %d ok, %d skipped, %d errors", total, ok, skipped, err)
    logger.info("  Relacoes: %d total", total_relations)
    logger.info("  Docs com datas: %d / %d", total_dates, total)
    logger.info("  Tempo: %.1f s", elapsed)
    logger.info("=" * 60)

    # Save report
    output = {
        "summary": summary,
        "results": results,
        "errors": errors,
    }
    output_path = args.output or "outputs/extractors_report.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Report salvo: %s", output_path)

    # Apply overrides (after extractors, to fix known OCR gaps)
    if not args.dry_run:
        try:
            from govy.legal.registry_overrides import apply_overrides
            ov_results = apply_overrides()
            if ov_results:
                logger.info("Overrides aplicados: %d", len(ov_results))
        except Exception:
            logger.warning("Overrides nao aplicados (arquivo nao encontrado ou erro)")


def main():
    parser = argparse.ArgumentParser(description="Run relation + date extractors on all documents")
    parser.add_argument("--limit", type=int, default=0, help="Max docs to process (0=all)")
    parser.add_argument("--doc-id", type=str, default=None, help="Process single doc_id")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
