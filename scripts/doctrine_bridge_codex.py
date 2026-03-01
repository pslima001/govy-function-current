"""
Script Ponte — Ingestão de Doutrinas do Codex no Pipeline V2

Le chunks pre-processados pelo Codex de kb-doutrina-raw (blob) e alimenta
os passos 3-6 do pipeline V2: classificacao verbatim -> extracao semantica ->
salvar processed -> report.

Uso:
  python scripts/doctrine_bridge_codex.py --dry-run --max-docs 1 --doctrine jacoby
  python scripts/doctrine_bridge_codex.py --skip-semantic --doctrine all
  python scripts/doctrine_bridge_codex.py --doctrine marcal --max-docs 5
  python scripts/doctrine_bridge_codex.py --force --doctrine all

Env vars:
  AZURE_STORAGE_CONNECTION_STRING  -- obrigatoria
  OPENAI_API_KEY                   -- opcional (sem ela, semantic_chunks=[])
  OPENAI_MODEL                     -- default gpt-4o-mini
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# ── path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from govy.doctrine.chunker import DoctrineChunk
from govy.doctrine.citation_extractor import extract_citation_meta
from govy.doctrine.verbatim_classifier import is_verbatim_legal_text
from govy.doctrine.semantic import extract_semantic_chunks_for_raw_chunks

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("doctrine_bridge")

# ── constants ─────────────────────────────────────────────────────────────────
CONTAINER_RAW = "kb-doutrina-raw"
CONTAINER_PROCESSED = "kb-doutrina-processed"

# Mapping: blob prefix → V2 metadata
# The blob prefix in kb-doutrina-raw matches local folder names from Codex output
DOCTRINE_META: Dict[str, Dict[str, str]] = {
    "marcal": {
        "autor": "Marçal Justen Filho",
        "obra": "Comentários à Lei de Licitações e Contratações Administrativas",
        "etapa_processo": "licitacao",
        "tema_principal": "LICITACAO",
        "blob_prefix": "marcal",
    },
    "jacoby": {
        "autor": "Jacoby Fernandes",
        "obra": "Lei de Licitações e Contratos Administrativos",
        "etapa_processo": "licitacao",
        "tema_principal": "LICITACAO",
        "blob_prefix": "jacoby",
    },
    "dalenogare": {
        "autor": "Felipe Dalenogare",
        "obra": "Manual de Licitações e Contratos Administrativos",
        "etapa_processo": "licitacao",
        "tema_principal": "LICITACAO",
        "blob_prefix": "dalenogare",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def _blob_exists(container_client, blob_name: str) -> bool:
    try:
        container_client.get_blob_client(blob_name).get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Erro ao verificar blob {blob_name}: {e}")
        return False


def _ensure_container(svc: BlobServiceClient, name: str) -> None:
    try:
        svc.get_container_client(name).get_container_properties()
    except ResourceNotFoundError:
        logger.info(f"Criando container: {name}")
        svc.get_container_client(name).create_container()


# ── discovery ─────────────────────────────────────────────────────────────────


def discover_doc_ids(container_client, blob_prefix: str) -> List[str]:
    """Descobre doc_ids listando blobs **/doc_metadata.json dentro do prefix."""
    doc_ids = []
    for blob in container_client.list_blobs(name_starts_with=blob_prefix + "/"):
        if blob.name.endswith("/doc_metadata.json"):
            # blob_prefix/doc_id/doc_metadata.json → extract doc_id
            parts = blob.name.split("/")
            if len(parts) >= 3:
                doc_id = parts[1]  # prefix/doc_id/doc_metadata.json
                doc_ids.append(doc_id)
    return sorted(set(doc_ids))


def load_doc_metadata(container_client, blob_prefix: str, doc_id: str) -> Dict[str, Any]:
    """Baixa e parseia doc_metadata.json."""
    blob_name = f"{blob_prefix}/{doc_id}/doc_metadata.json"
    data = container_client.get_blob_client(blob_name).download_blob().readall()
    return json.loads(data.decode("utf-8"))


def load_codex_chunks(container_client, blob_prefix: str, doc_id: str) -> List[Dict[str, Any]]:
    """Baixa todos os chunks/*.json de um doc_id, ordenados por chunk_index."""
    chunk_prefix = f"{blob_prefix}/{doc_id}/chunks/"
    chunks = []
    for blob in container_client.list_blobs(name_starts_with=chunk_prefix):
        if blob.name.endswith(".json"):
            data = container_client.get_blob_client(blob.name).download_blob().readall()
            chunk = json.loads(data.decode("utf-8"))
            chunks.append(chunk)
    # Sort by chunk_index
    chunks.sort(key=lambda c: c.get("chunk_index", 0))
    return chunks


# ── conversion ────────────────────────────────────────────────────────────────


def codex_chunk_to_doctrine_chunk(codex_chunk: Dict[str, Any], order: int) -> DoctrineChunk:
    """Converte um chunk do Codex em DoctrineChunk do pipeline V2.

    Marcal: sem content_hash → gerar a partir do text.
    Jacoby/Dalenogare: já tem content_hash.
    """
    text = (codex_chunk.get("text") or "").strip()
    content_hash = codex_chunk.get("content_hash") or _sha256_str(text)
    chunk_id = f"doctrine_{order}_{content_hash[:16]}"
    return DoctrineChunk(
        chunk_id=chunk_id,
        order=order,
        content_raw=text,
        content_hash=content_hash,
    )


# ── processing ────────────────────────────────────────────────────────────────


def process_single_doc(
    raw_container,
    proc_container,
    blob_prefix: str,
    doc_id: str,
    meta_info: Dict[str, str],
    *,
    skip_semantic: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """Processa um doc_id do Codex e produz doctrine_processed_v2."""
    stage = meta_info["etapa_processo"]
    theme_field = meta_info["tema_principal"]
    theme_path = theme_field.lower()

    # 1. Load metadata
    doc_meta = load_doc_metadata(raw_container, blob_prefix, doc_id)
    source_sha = doc_meta.get("source_sha256", "")
    source_filename = doc_meta.get("source_filename", "")

    if not source_sha:
        logger.warning(f"  [{doc_id}] sem source_sha256 em metadata, gerando do doc_id")
        source_sha = _sha256_str(doc_id)

    # 2. Check idempotency
    processed_blob_name = f"{stage}/{theme_path}/{source_sha}.json"
    if not force and not dry_run and _blob_exists(proc_container, processed_blob_name):
        logger.info(f"  [{doc_id}] ja processado: {processed_blob_name} (skip)")
        return {"status": "already_processed", "doc_id": doc_id}

    # 3. Load Codex chunks
    codex_chunks = load_codex_chunks(raw_container, blob_prefix, doc_id)
    if not codex_chunks:
        logger.warning(f"  [{doc_id}] nenhum chunk encontrado, pulando")
        return {"status": "no_chunks", "doc_id": doc_id}

    # 4. Convert to DoctrineChunk
    doctrine_chunks: List[DoctrineChunk] = []
    for i, cc in enumerate(codex_chunks):
        doctrine_chunks.append(codex_chunk_to_doctrine_chunk(cc, order=i))

    # 5. Build raw_chunk_docs
    raw_chunk_docs: List[Dict[str, Any]] = []
    for ch in doctrine_chunks:
        raw_chunk_docs.append({
            "id": f"doutrina_raw::{source_sha}::{ch.chunk_id}",
            "doc_type": "doutrina_raw",
            "procedural_stage": stage.upper(),
            "tema_principal": theme_field,
            "chunk_id": ch.chunk_id,
            "order": ch.order,
            "content_raw": ch.content_raw,
            "content_hash": ch.content_hash,
            "source_sha": source_sha,
            "created_at": _utc_now_iso(),
        })

    # 6. Verbatim classification + separation
    verbatim_legal_chunks: List[Dict[str, Any]] = []
    doctrine_raw_for_semantic: List[DoctrineChunk] = []

    for ch in doctrine_chunks:
        if is_verbatim_legal_text(ch.content_raw):
            verbatim_legal_chunks.append({
                "id": f"verbatim::{source_sha}::{ch.chunk_id}",
                "doc_type": "jurisprudencia_verbatim",
                "content_raw": ch.content_raw,
                "citation_meta": extract_citation_meta(ch.content_raw),
                "source_refs": {
                    "source_sha": source_sha,
                    "raw_chunk_id": ch.chunk_id,
                    "raw_content_hash": ch.content_hash,
                },
                "created_at": _utc_now_iso(),
            })
        else:
            doctrine_raw_for_semantic.append(ch)

    # 7. Semantic extraction (optional)
    semantic_chunks: List[Dict[str, Any]] = []
    if not skip_semantic:
        semantic_chunks = extract_semantic_chunks_for_raw_chunks(
            raw_chunks=doctrine_raw_for_semantic,
            procedural_stage=stage.upper(),
            tema_principal=theme_field,
            source_sha=source_sha,
            review_status_default="PENDING",
        )

    # 8. Compute total chars from all original Codex chunk texts
    total_chars = sum(len(cc.get("text", "")) for cc in codex_chunks)

    # 9. Build payload
    payload = {
        "kind": "doctrine_processed_v2",
        "status": "processed",
        "generated_at": _utc_now_iso(),
        "source": {
            "container": CONTAINER_RAW,
            "blob_name": f"{blob_prefix}/{doc_id}/doc_metadata.json",
            "source_sha": source_sha,
        },
        "context": {
            "etapa_processo": stage,
            "tema_principal": theme_field,
        },
        "internal_meta": {
            "autor": meta_info["autor"],
            "obra": meta_info["obra"],
            "edicao": "",
            "ano": 0,
            "capitulo": "",
            "secao": "",
        },
        "stats": {
            "paragraphs": len(codex_chunks),
            "chars": total_chars,
            "raw_chunks": len(raw_chunk_docs),
            "semantic_chunks": len(semantic_chunks),
            "verbatim_legal_chunks": len(verbatim_legal_chunks),
            "incertos": sum(1 for c in semantic_chunks if c.get("coverage_status") == "INCERTO"),
        },
        "raw_chunks": raw_chunk_docs,
        "semantic_chunks": semantic_chunks,
        "verbatim_legal_chunks": verbatim_legal_chunks,
        "public_knowledge": None,
    }

    # 10. Upload or dry-run
    if dry_run:
        logger.info(
            f"  [{doc_id}] DRY-RUN: raw={len(raw_chunk_docs)} verbatim={len(verbatim_legal_chunks)} "
            f"semantic={len(semantic_chunks)} -> {processed_blob_name}"
        )
    else:
        blob_client = proc_container.get_blob_client(processed_blob_name)
        blob_client.upload_blob(
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )
        logger.info(
            f"  [{doc_id}] UPLOADED: raw={len(raw_chunk_docs)} verbatim={len(verbatim_legal_chunks)} "
            f"semantic={len(semantic_chunks)} -> {processed_blob_name}"
        )

    return {
        "status": "processed",
        "doc_id": doc_id,
        "raw_chunks": len(raw_chunk_docs),
        "verbatim_legal_chunks": len(verbatim_legal_chunks),
        "semantic_chunks": len(semantic_chunks),
        "incertos": payload["stats"]["incertos"],
    }


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Bridge: Codex chunks -> Pipeline V2 processed")
    parser.add_argument("--doctrine", default="all", choices=["marcal", "jacoby", "dalenogare", "all"],
                        help="Qual doutrina processar (default: all)")
    parser.add_argument("--max-docs", type=int, default=999, help="Max docs a processar (default: 999)")
    parser.add_argument("--dry-run", action="store_true", help="Nao faz upload, so mostra o que faria")
    parser.add_argument("--skip-semantic", action="store_true", help="Pular OpenAI (so verbatim + raw)")
    parser.add_argument("--force", action="store_true", help="Reprocessar mesmo se ja existe em processed")
    args = parser.parse_args()

    # Connection string
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logger.error("AZURE_STORAGE_CONNECTION_STRING nao definida")
        sys.exit(1)

    svc = BlobServiceClient.from_connection_string(conn_str)
    _ensure_container(svc, CONTAINER_RAW)
    _ensure_container(svc, CONTAINER_PROCESSED)
    raw_cc = svc.get_container_client(CONTAINER_RAW)
    proc_cc = svc.get_container_client(CONTAINER_PROCESSED)

    # Doctrines to process
    if args.doctrine == "all":
        doctrines = list(DOCTRINE_META.keys())
    else:
        doctrines = [args.doctrine]

    # Track totals
    totals = {
        "docs_processed": 0,
        "docs_skipped": 0,
        "docs_no_chunks": 0,
        "docs_error": 0,
        "raw_chunks": 0,
        "verbatim": 0,
        "semantic": 0,
        "incertos": 0,
    }
    remaining_docs = args.max_docs
    t0 = time.time()

    for doctrine_key in doctrines:
        meta = DOCTRINE_META[doctrine_key]
        blob_prefix = meta["blob_prefix"]
        logger.info(f"=== {doctrine_key.upper()} (prefix={blob_prefix}) ===")

        doc_ids = discover_doc_ids(raw_cc, blob_prefix)
        logger.info(f"  Encontrados {len(doc_ids)} doc_ids")

        for doc_id in doc_ids:
            if remaining_docs <= 0:
                logger.info("  max-docs atingido, parando")
                break
            remaining_docs -= 1

            try:
                result = process_single_doc(
                    raw_cc, proc_cc, blob_prefix, doc_id, meta,
                    skip_semantic=args.skip_semantic,
                    dry_run=args.dry_run,
                    force=args.force,
                )
                status = result.get("status", "unknown")
                if status == "processed":
                    totals["docs_processed"] += 1
                    totals["raw_chunks"] += result.get("raw_chunks", 0)
                    totals["verbatim"] += result.get("verbatim_legal_chunks", 0)
                    totals["semantic"] += result.get("semantic_chunks", 0)
                    totals["incertos"] += result.get("incertos", 0)
                elif status == "already_processed":
                    totals["docs_skipped"] += 1
                elif status == "no_chunks":
                    totals["docs_no_chunks"] += 1
            except Exception as e:
                logger.error(f"  [{doc_id}] ERRO: {e}")
                totals["docs_error"] += 1

    elapsed = time.time() - t0
    logger.info("=" * 60)
    logger.info("REPORT FINAL")
    logger.info(f"  Tempo: {elapsed:.1f}s")
    logger.info(f"  Docs processados:   {totals['docs_processed']}")
    logger.info(f"  Docs skipped:       {totals['docs_skipped']}")
    logger.info(f"  Docs sem chunks:    {totals['docs_no_chunks']}")
    logger.info(f"  Docs com erro:      {totals['docs_error']}")
    logger.info(f"  Raw chunks total:   {totals['raw_chunks']}")
    logger.info(f"  Verbatim chunks:    {totals['verbatim']}")
    logger.info(f"  Semantic chunks:    {totals['semantic']}")
    logger.info(f"  Incertos:           {totals['incertos']}")
    logger.info(f"  Dry-run: {args.dry_run} | Skip-semantic: {args.skip_semantic} | Force: {args.force}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
