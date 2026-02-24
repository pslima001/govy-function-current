# govy/legal/pipeline.py
"""
Pipeline de ingestao de legislacao: blob → extract text → chunk → write DB.

Orquestra:
  1. Lista blobs no container normas-juridicas-raw
  2. Baixa cada documento
  3. Extrai texto (PDF/DOCX)
  4. Chunka estruturalmente (artigos/paragrafos)
  5. Grava no Postgres (legal_document + legal_provision + legal_chunk)

Blob path convention:
  federal/BR/{tipo_plural}/{doc_id}/source.{pdf|docx}
  Ex: federal/BR/instrucoes_normativas/in_62_2021_federal_br/source.pdf
"""
from __future__ import annotations

import os
import json
import logging
import re
from typing import List, Optional, Tuple

from azure.storage.blob import BlobServiceClient, ContainerClient
from govy.legal.models import LegalDocumentRow, ExtractionResult
from govy.legal.text_extractor import extract
from govy.legal.legal_chunker import chunk_legal_text
from govy.legal.db_writer import write_document

logger = logging.getLogger(__name__)

RAW_CONTAINER = "normas-juridicas-raw"
STORAGE_ACCOUNT = "stgovyparsetestsponsor"
DEFAULT_JURISDICTION = "federal_br"


# ── Container client factory ──────────────────────────────────────────────────

def _get_container(container_name: str = RAW_CONTAINER) -> ContainerClient:
    """
    Retorna ContainerClient.
    Usa AZURE_STORAGE_CONNSTR_SPONSOR (connection string) se disponivel,
    senao fallback para DefaultAzureCredential via azure_clients.
    """
    connstr = os.environ.get("AZURE_STORAGE_CONNSTR_SPONSOR", "")
    if connstr:
        svc = BlobServiceClient.from_connection_string(connstr)
        return svc.get_container_client(container_name)
    else:
        from govy.utils.azure_clients import get_container_client
        return get_container_client(container_name, STORAGE_ACCOUNT)


# ── Helpers para parse de metadata do blob path ───────────────────────────────

# Map plural folder name → doc_type singular
_FOLDER_TO_TYPE = {
    "instrucoes_normativas": "instrucao_normativa",
    "portarias": "portaria",
    "resolucoes": "resolucao",
    "leis": "lei",
    "leis_complementares": "lei_complementar",
    "decretos": "decreto",
    "medidas_provisorias": "medida_provisoria",
    "emendas_constitucionais": "emenda_constitucional",
}

_TYPE_DISPLAY = {
    "instrucao_normativa": "IN",
    "portaria": "Portaria",
    "resolucao": "Resolucao",
    "lei": "Lei",
    "lei_complementar": "LC",
    "decreto": "Decreto",
    "medida_provisoria": "MP",
    "emenda_constitucional": "EC",
    "outro": "Doc",
}


def _parse_blob_path(blob_name: str) -> dict:
    """
    Extrai metadata do path do blob.

    Path: federal/BR/{tipo_plural}/{doc_id}/source.{ext}
    Returns: {doc_id, doc_type, number, year, title_short, filename}
    """
    parts = blob_name.replace("\\", "/").split("/")

    # Fallback defaults
    result = {
        "doc_id": None,
        "doc_type": "outro",
        "number": None,
        "year": None,
        "title_short": None,
        "filename": parts[-1] if parts else blob_name,
    }

    if len(parts) >= 4:
        tipo_plural = parts[2]
        doc_id = parts[3]
        result["doc_id"] = doc_id
        result["doc_type"] = _FOLDER_TO_TYPE.get(tipo_plural, "outro")

        # Parse doc_id: in_62_2021_federal_br → number=62, year=2021
        m = re.match(r"^[a-z]+_(\d+)_(\d{4})_", doc_id)
        if m:
            result["number"] = m.group(1)
            result["year"] = int(m.group(2))
        else:
            # Tenta: tipo_numero_jurisdicao (sem ano)
            m2 = re.match(r"^[a-z]+_(\d+)_", doc_id)
            if m2:
                result["number"] = m2.group(1)

    # Title short
    if result["doc_type"] and result["number"]:
        prefix = _TYPE_DISPLAY.get(result["doc_type"], "Doc")
        num = result["number"]
        if len(num) > 3 and num.isdigit():
            num = f"{int(num):,}".replace(",", ".")
        if result["year"]:
            result["title_short"] = f"{prefix} {num}/{result['year']}"
        else:
            result["title_short"] = f"{prefix} {num}"
    elif result["doc_id"]:
        result["title_short"] = result["doc_id"]

    return result


# ── Pipeline principal ─────────────────────────────────────────────────────────

def list_raw_blobs(container_name: str = RAW_CONTAINER) -> List[dict]:
    """Lista todos os blobs no container raw com metadata."""
    container = _get_container(container_name)
    blobs = []
    for blob in container.list_blobs():
        name = blob.name
        if not (name.lower().endswith(".pdf") or name.lower().endswith(".docx")):
            continue
        blobs.append({
            "name": name,
            "size": blob.size,
            "last_modified": str(blob.last_modified) if blob.last_modified else None,
        })
    logger.info("Container %s: %d blobs encontrados", container_name, len(blobs))
    return blobs


def process_one(
    blob_name: str,
    container_name: str = RAW_CONTAINER,
    dry_run: bool = False,
    registry_entry: Optional[dict] = None,
) -> dict:
    """
    Processa um documento: download → extract → chunk → write DB.

    Args:
        blob_name: nome do blob no container
        container_name: container no blob storage
        dry_run: se True, nao grava no DB
        registry_entry: metadata override (doc_id, doc_type, number, year, title)

    Returns:
        dict com resultado do processamento
    """
    logger.info("Processando: %s (dry_run=%s)", blob_name, dry_run)

    # 1. Download
    container = _get_container(container_name)
    blob_client = container.get_blob_client(blob_name)
    file_bytes = blob_client.download_blob().readall()
    logger.info("Download OK: %s (%d bytes)", blob_name, len(file_bytes))

    # 2. Extract text
    filename = blob_name.split("/")[-1]
    extraction = extract(file_bytes, filename)
    if not extraction.text or extraction.char_count < 100:
        logger.warning("Texto muito curto para %s: %d chars", blob_name, extraction.char_count)
        return {
            "blob_name": blob_name,
            "status": "skipped",
            "reason": f"texto muito curto ({extraction.char_count} chars)",
        }

    # 3. Parse metadata — from path or registry override
    if registry_entry:
        doc_id = registry_entry.get("doc_id")
        doc_type = registry_entry.get("doc_type", "outro")
        number = registry_entry.get("number")
        year = registry_entry.get("year")
        title = registry_entry.get("title", blob_name)
        title_short = registry_entry.get("title_short", doc_id or blob_name)
    else:
        meta = _parse_blob_path(blob_name)
        doc_id = meta["doc_id"]
        doc_type = meta["doc_type"]
        number = meta["number"]
        year = meta["year"]
        title_short = meta["title_short"] or doc_id or blob_name
        title = title_short

    if not doc_id:
        # Fallback: use filename stem
        doc_id = filename.rsplit(".", 1)[0].replace(" ", "_").lower()
        logger.warning("doc_id gerado por fallback: %s", doc_id)

    # 4. Chunk
    provisions, chunks = chunk_legal_text(extraction.text, doc_id, title_short)

    # 5. Build document row
    doc = LegalDocumentRow(
        doc_id=doc_id,
        jurisdiction_id=DEFAULT_JURISDICTION,
        doc_type=doc_type,
        number=number,
        year=year,
        title=title,
        source_blob_path=f"{container_name}/{blob_name}",
        source_format=extraction.source_format,
        text_sha256=extraction.sha256,
        char_count=extraction.char_count,
        provisions=provisions,
        chunks=chunks,
    )

    result = {
        "blob_name": blob_name,
        "doc_id": doc_id,
        "doc_type": doc_type,
        "number": number,
        "year": year,
        "char_count": extraction.char_count,
        "provisions": len(provisions),
        "chunks": len(chunks),
        "extractor": extraction.extractor,
    }

    # 6. Write to DB
    if dry_run:
        result["status"] = "dry_run"
        logger.info("DRY RUN: %s → %d provisions, %d chunks", doc_id, len(provisions), len(chunks))
    else:
        db_result = write_document(doc)
        result["status"] = "ok"
        result["db_result"] = db_result
        logger.info("GRAVADO: %s → %d provisions, %d chunks", doc_id, len(provisions), len(chunks))

    return result


def process_batch(
    limit: int = 0,
    dry_run: bool = False,
    doc_id_filter: Optional[str] = None,
    registry: Optional[dict] = None,
) -> List[dict]:
    """
    Processa batch de documentos.

    Args:
        limit: maximo de docs a processar (0 = todos)
        dry_run: se True, nao grava no DB
        doc_id_filter: processar apenas um doc_id especifico
        registry: dict de blob_name → metadata override

    Returns:
        lista de resultados
    """
    blobs = list_raw_blobs()
    results = []
    errors = []

    if doc_id_filter:
        # Filtra pelo doc_id no path
        blobs = [
            b for b in blobs
            if doc_id_filter in b["name"]
        ]

    if limit > 0:
        blobs = blobs[:limit]

    total = len(blobs)
    logger.info("Batch: %d documentos para processar (dry_run=%s)", total, dry_run)

    for i, blob_info in enumerate(blobs, 1):
        blob_name = blob_info["name"]
        logger.info("[%d/%d] %s", i, total, blob_name)

        entry = registry.get(blob_name) if registry else None

        try:
            result = process_one(
                blob_name=blob_name,
                dry_run=dry_run,
                registry_entry=entry,
            )
            results.append(result)
        except Exception as e:
            logger.exception("ERRO em %s: %s", blob_name, e)
            errors.append({"blob_name": blob_name, "error": str(e)})

    ok = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    dry = sum(1 for r in results if r.get("status") == "dry_run")

    logger.info(
        "Batch completo: %d total, %d ok, %d skipped, %d dry_run, %d errors",
        total, ok, skipped, dry, len(errors),
    )

    return results
