from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List

from azure.storage.blob import BlobServiceClient, ContentSettings

from govy.doctrine.reader_docx import read_docx_bytes
from govy.doctrine.chunker import chunk_paragraphs


@dataclass(frozen=True)
class DoctrineIngestRequest:
    blob_name: str
    etapa_processo: str
    tema_principal: str

    # metadados internos (NUNCA expor ao usuário)
    autor: str
    obra: str
    edicao: str
    ano: int
    capitulo: str
    secao: str

    force_reprocess: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _safe_stage(s: str) -> str:
    s = (s or "").strip().lower()
    return s or "habilitacao"


def _safe_theme(s: str) -> str:
    s = (s or "").strip().lower()
    return s or "tema"


def _processed_blob_name(stage: str, theme: str, source_sha: str) -> str:
    return f"{stage}/{theme}/{source_sha}.json"


def ingest_doctrine_process_once(
    blob_service: BlobServiceClient,
    container_source: str,
    container_processed: str,
    req: DoctrineIngestRequest,
) -> Dict[str, Any]:
    """
    Processa UMA VEZ:
      - baixa DOCX do container_source
      - extrai texto bruto
      - chunk bruto
      - salva JSON processado no container_processed

    Regras:
      - NÃO usa LLM
      - NÃO infere
      - NÃO inventa
      - NÃO reescreve sentido
    """
    stage = _safe_stage(req.etapa_processo)
    theme = _safe_theme(req.tema_principal)

    src_container = blob_service.get_container_client(container_source)
    src_blob = src_container.get_blob_client(req.blob_name)
    docx_bytes = src_blob.download_blob().readall()

    source_sha = _sha256_bytes(docx_bytes)
    processed_name = _processed_blob_name(stage, theme, source_sha)

    proc_container = blob_service.get_container_client(container_processed)
    proc_blob = proc_container.get_blob_client(processed_name)

    if (not req.force_reprocess) and proc_blob.exists():
        return {
            "status": "already_processed",
            "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
            "processed": {"container": container_processed, "blob_name": processed_name},
        }

    raw = read_docx_bytes(docx_bytes)
    chunks = chunk_paragraphs(raw.paragraphs)

    chunk_docs: List[Dict[str, Any]] = []
    for ch in chunks:
        chunk_docs.append(
            {
                "id": f"doutrina::{source_sha}::{ch.chunk_id}",
                "doc_type": "doutrina",
                "procedural_stage": stage.upper(),
                "tema_principal": theme,
                "chunk_id": ch.chunk_id,
                "order": ch.order,
                "content_raw": ch.content_raw,  # interno (não é para UI)
                "content_hash": ch.content_hash,
                "source_sha": source_sha,
                "created_at": _utc_now_iso(),
            }
        )

    payload = {
        "kind": "doctrine_processed_v1",
        "status": "processed",
        "generated_at": _utc_now_iso(),
        "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
        "context": {"etapa_processo": stage, "tema_principal": theme},
        "internal_meta": {
            "autor": req.autor,
            "obra": req.obra,
            "edicao": req.edicao,
            "ano": req.ano,
            "capitulo": req.capitulo,
            "secao": req.secao,
        },
        "stats": {"paragraphs": len(raw.paragraphs), "chars": len(raw.text), "chunks": len(chunk_docs)},
        "chunks": chunk_docs,
        "public_knowledge": None,
    }

    proc_blob.upload_blob(
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
    )

    return {
        "status": "processed",
        "source": {"container": container_source, "blob_name": req.blob_name, "source_sha": source_sha},
        "processed": {"container": container_processed, "blob_name": processed_name},
        "stats": payload["stats"],
    }
