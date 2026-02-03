from __future__ import annotations
import json
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from govy.doctrine.reader_docx import read_docx_bytes
from govy.doctrine.chunker import chunk_paragraphs
from govy.doctrine.verbatim_classifier import is_verbatim_legal_text
from govy.doctrine.citation_extractor import extract_citation_meta
from govy.doctrine.semantic import extract_semantic_chunks_for_raw_chunks

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DoctrineIngestRequest:
    blob_name: str
    etapa_processo: str
    tema_principal: str
    autor: str = ""
    obra: str = ""
    edicao: str = ""
    ano: int = 0
    capitulo: str = ""
    secao: str = ""
    force_reprocess: bool = False

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _safe_stage(s: str) -> str:
    s = (s or "").strip().lower()
    return s or "habilitacao"

def _safe_theme(s: str) -> str:
    """Retorna tema normalizado em UPPER.
    Path do blob usa .lower() separadamente."""
    s = (s or "").strip()
    if not s: 
        return "TEMA"
    s = re.sub(r"[\s\-\/]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()

def _processed_blob_name(stage: str, theme: str, source_sha: str) -> str:
    return f"{stage}/{theme}/{source_sha}.json"

def _blob_exists(blob_client) -> bool:
    try:
        blob_client.get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Erro ao verificar existência do blob: {e}")
        return False

def _ensure_container_exists(blob_service: BlobServiceClient, container_name: str) -> None:
    try:
        container_client = blob_service.get_container_client(container_name)
        container_client.get_container_properties()
        logger.info(f"Container existe: {container_name}")
    except ResourceNotFoundError:
        logger.info(f"Criando container: {container_name}")
        container_client = blob_service.get_container_client(container_name)
        container_client.create_container()
    except Exception as e:
        logger.error(f"Erro ao verificar/criar container {container_name}: {e}")
        raise

def ingest_doctrine_process_once(
    blob_service: BlobServiceClient,
    container_source: str,
    container_processed: str,
    req: DoctrineIngestRequest,
) -> Dict[str, Any]:
    logger.info(f"Iniciando processamento: {req.blob_name}")
    _ensure_container_exists(blob_service, container_source)
    _ensure_container_exists(blob_service, container_processed)
    stage = _safe_stage(req.etapa_processo)
    theme_field = _safe_theme(req.tema_principal)        # UPPER, usado no JSON/chunks
    theme_path = theme_field.lower()                 # lower, usado no path do blob
    src_container = blob_service.get_container_client(container_source)
    src_blob = src_container.get_blob_client(req.blob_name)
    try:
        docx_bytes = src_blob.download_blob().readall()
    except ResourceNotFoundError:
        logger.error(f"Blob ã ncontrado: {req.blob_name}")
        raise ValueError(f"Blob não encontrado: {req.blob_name}")
    except Exception as e:
        logger.error(f"Erro ao baixar blob: {e}")
        raise
    source_sha = _sha256_bytes(docx_bytes)
    processed_name = _processed_blob_name(stage, theme_path, source_sha)
    proc_container = blob_service.get_container_client(container_processed)
    proc_blob = proc_container.get_blob_client(processed_name)
    if (not req.force_reprocess) and _blob_exists(proc_blob):
        logger.info(f"Já processado: {processed_name}")
        return {
            "status": "already_processed",
            "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
            "processed": {"container": container_processed, "blob_name": processed_name},
        }
    logger.info("Extraindo texto do DOCX...")
    raw = read_docx_bytes(docx_bytes)
    logger.info(f"Criando chunks brutos (paragraphs: {len(raw.paragraphs)}...")
    chunks = chunk_paragraphs(raw.paragraphs)
    raw_chunk_docs: List[Dict[str, Any]] = []
    for ch in chunks:
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
    verbatim_legal_chunks: List[Dict[str, Any]] = []
    doctrine_raw_chunks = []
    for ch in chunks:
        if is_verbatim_legal_text(ch.content_raw):
            verbatim_legal_chunks.append({
                "id": f"verbatim::{source_sha}::{ch.chunk_id}",
                "doc_type": "jurisprudencia_verbatim",
                "content_raw": ch.content_raw,
                "citation_meta": extract_citation_meta(ch.content_raw),
                "source_refs": {"source_sha": source_sha, "raw_chunk_id": ch.chunk_id, "raw_content_hash": ch.content_hash},
                "created_at": _utc_now_iso(),
            })
        else:
            doctrine_raw_chunks.append(ch)
    logger.info(f"Separação concluída: verbatim_legal_chunks={len(verbatim_legal_chunks)} | doctrine_raw_chunks={len(doctrine_raw_chunks)}")
    logger.info("Gerando semantic_chunks (doutrina) via OpenAI (process once)...")
    semantic_chunks = extract_semantic_chunks_for_raw_chunks(
        raw_chunks=doctrine_raw_chunks,
        procedural_stage=stage.upper(),
        tema_principal=theme_field,
        source_sha=source_sha,
        review_status_default="PENDING",
    )
    payload = {
        "kind": "doctrine_processed_v2",
        "status": "processed",
        "generated_at": _utc_now_iso(),
        "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
        "context": {"etapa_processo": stage, "tema_principal": theme_field},
        "internal_meta": {
            "autor": req.autor, "obra": req.obra, "edicao": req.edicao,
            "ano": req.ano, "capitulo": req.capitulo, "secao": req.secao,
        },
        "stats": {
            "paragraphs": len(raw.paragraphs),
            "chars": len(raw.text),
            "raw_chunks": len(raw_chunk_docs),
            "semantic_chunks": len(semantic_chunks),
            "verbatim_legal_chunks": len(verbatim_legal_chunks),
            "incertos": sum(1 for c in semantic_chunks if (c.get("coverage_status") == "INCERTO")),
        },
        "raw_chunks": raw_chunk_docs,
        "semantic_chunks": semantic_chunks,
        "verbatim_legal_chunks": verbatim_legal_chunks,
        "public_knowledge": None,
    }
    logger.info(f"Salvando resultado em: {processed_name}")
    try:
        proc_blob.upload_blob(
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )
    except Exception as e:
        logger.error(f"Erro ao salvar blob processado: {e}")
        raise
    logger.info(f"Processamento concluído: raw_chunks={len(raw_chunk_docs)} semantic_chunks={len(semantic_chunks)} verbatim_legal_chunks={len(verbatim_legal_chunks)}")
    return {
        "status": "processed",
        "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
        "processed": {"container": container_processed, "blob_name": processed_name},
        "stats": payload["stats"],
    }
