"""
govy/api/tce_queue_handler.py
Handler para Queue Trigger que processa PDFs de jurisprudência TCE.

Fluxo:
  1. /api/kb/juris/enqueue-tce  →  lista blobs, enfileira 1 msg/PDF
  2. Queue parse-tce-queue      →  baixa PDF, parseia, mapeia, grava JSON em kb-raw
  3. (futuro) Queue index-kb-raw →  lê JSON, gera embedding, indexa no Azure Search

Dependências: PyMuPDF (fitz), pdfplumber (fallback)

Storage accounts:
  - TCE_STORAGE_CONNECTION  → sttcejurisprudencia (leitura PDFs)
  - AzureWebJobsStorage     → stgovyparsetestsponsor (escrita kb-raw, filas)
"""

import json
import logging
import os
from datetime import datetime

from azure.storage.blob import BlobServiceClient, ContentSettings
from govy.config.tribunal_registry import get_config
from govy.utils.azure_clients import get_blob_service_client as _get_main_blob_svc

# Imports locais (lazy para evitar cold start pesado)
# tce_parser_v3 e mapping_tce_to_kblegal devem estar em govy/api/

logger = logging.getLogger(__name__)

# Container onde gravamos os JSONs processados (na conta stgovyparsetestsponsor)
KB_RAW_CONTAINER = "kb-raw"


def _get_tce_blob_service() -> BlobServiceClient:
    """Client para sttcejurisprudencia (leitura de PDFs)."""
    conn_str = os.environ.get("TCE_STORAGE_CONNECTION", "")
    if not conn_str:
        raise ValueError("TCE_STORAGE_CONNECTION not configured")
    return BlobServiceClient.from_connection_string(conn_str)  # ALLOW_CONNECTION_STRING_OK


def _get_main_blob_service() -> BlobServiceClient:
    """Client para stgovyparsetestsponsor (kb-raw, filas)."""
    return _get_main_blob_svc()


# ============================================================
# 1. ENQUEUE: lista blobs e enfileira mensagens
# ============================================================

def handle_enqueue_tce(req_body: dict) -> dict:
    """
    Lista PDFs no container tce-jurisprudencia (conta sttcejurisprudencia)
    e retorna lista de mensagens para enfileirar.

    Parâmetros (body JSON):
      prefix: filtro de prefixo no container (default: "tce-sp/acordaos/")
      limit: máximo de PDFs a enfileirar (default: 0 = todos)
      skip_existing: se True, pula PDFs que já têm JSON em kb-raw (default: True)

    Retorna: { enqueued: int, skipped: int, messages: [...] }
    """
    tribunal_id = req_body.get("tribunal_id", "tce-sp")
    cfg = get_config(tribunal_id)

    default_prefix = f"{cfg.raw_prefix}acordaos/"
    prefix = req_body.get("prefix", default_prefix)
    limit = int(req_body.get("limit", 0))
    skip_existing = req_body.get("skip_existing", True)

    # PDFs estão em sttcejurisprudencia
    tce_service = _get_tce_blob_service()
    source_container = tce_service.get_container_client(cfg.container_raw)

    # JSONs processados estão em stgovyparsetestsponsor
    main_service = _get_main_blob_service()
    raw_container = main_service.get_container_client(KB_RAW_CONTAINER)

    # Garantir que kb-raw existe
    try:
        raw_container.create_container()
    except Exception:
        pass  # já existe

    # Set de JSONs já existentes (para skip)
    existing_keys = set()
    if skip_existing:
        try:
            for blob in raw_container.list_blobs(name_starts_with="tce-"):
                existing_keys.add(blob.name)
        except Exception as e:
            logger.warning(f"Erro listando kb-raw: {e}")

    messages = []
    skipped = 0

    for blob in source_container.list_blobs(name_starts_with=prefix):
        if not blob.name.lower().endswith(".pdf"):
            continue
        if ".voto." in blob.name.lower():
            continue

        # Nome determinístico do JSON de saída
        json_key = _blob_path_to_json_key(blob.name)

        if skip_existing and json_key in existing_keys:
            skipped += 1
            continue

        msg = {
            "tribunal_id": tribunal_id,
            "blob_path": blob.name,
            "blob_etag": blob.etag or "",
            "json_key": json_key,
        }
        messages.append(msg)

        if limit > 0 and len(messages) >= limit:
            break

    return {
        "status": "success",
        "tribunal_id": tribunal_id,
        "enqueued": len(messages),
        "skipped": skipped,
        "total_existing": len(existing_keys),
        "messages": messages,
    }


def _blob_path_to_json_key(blob_path: str) -> str:
    """
    Converte path do PDF para nome do JSON em kb-raw.
    Ex: tce-sp/acordaos/10026_989_24_acordao.pdf → tce-sp--acordaos--10026_989_24_acordao.json
    """
    import re
    # Remove extensão
    name = blob_path.rsplit(".", 1)[0]
    # Substitui / por --
    name = name.replace("/", "--")
    # Remove caracteres inválidos
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return f"{name}.json"


# ============================================================
# 2. PARSE: processa 1 PDF da fila
# ============================================================

def handle_parse_tce_pdf(msg_json: str) -> dict:
    """
    Processa 1 mensagem da fila parse-tce-queue.

    Mensagem esperada (JSON):
      { "blob_path": "...", "blob_etag": "...", "json_key": "..." }

    Ações:
      1. Baixa PDF de sttcejurisprudencia/tce-jurisprudencia
      2. Extrai texto com PyMuPDF/pdfplumber
      3. Parseia com tce_parser_v3 (25 campos)
      4. Mapeia para kb-legal (19 campos) com mapping_tce_to_kblegal
      5. Grava JSON em stgovyparsetestsponsor/kb-raw/{json_key}

    Retorna: dict com status
    """
    # Import lazy para cold start
    from govy.api.tce_parser_v3 import parse_pdf_bytes
    from govy.api.mapping_tce_to_kblegal import transform_parser_to_kblegal

    msg = json.loads(msg_json) if isinstance(msg_json, str) else msg_json

    blob_path = msg["blob_path"]
    blob_etag = msg.get("blob_etag", "")
    json_key = msg.get("json_key", _blob_path_to_json_key(blob_path))

    # Resolve tribunal config (explicit or inferred from blob_path)
    tribunal_id = msg.get("tribunal_id")
    if not tribunal_id:
        tribunal_id = blob_path.split("/")[0] if "/" in blob_path else "tce-sp"
    cfg = get_config(tribunal_id)

    logger.info(f"[parse-tce] Processando: {blob_path} (tribunal={tribunal_id})")

    # 1. Baixar PDF de sttcejurisprudencia
    try:
        tce_service = _get_tce_blob_service()
        source = tce_service.get_container_client(cfg.container_raw)
        pdf_bytes = source.get_blob_client(blob_path).download_blob().readall()
        logger.info(f"[parse-tce] PDF baixado: {len(pdf_bytes)} bytes")
    except Exception as e:
        logger.error(f"[parse-tce] Erro baixando {blob_path}: {e}")
        return {"status": "error", "error": f"download_failed: {e}", "blob_path": blob_path}

    if len(pdf_bytes) < 100:
        logger.warning(f"[parse-tce] PDF muito pequeno ({len(pdf_bytes)} bytes), pulando")
        return {"status": "skipped", "reason": "pdf_too_small", "blob_path": blob_path}

    # 2. Parsear com tce_parser_v3
    try:
        parser_output = parse_pdf_bytes(pdf_bytes, include_text=False)
        logger.info(f"[parse-tce] Parser OK - {sum(1 for v in parser_output.values() if v != '__MISSING__' and v != [])}/25 campos")
    except Exception as e:
        logger.error(f"[parse-tce] Erro no parser: {e}")
        return {"status": "error", "error": f"parse_failed: {e}", "blob_path": blob_path}

    # 3. Mapear para kb-legal
    try:
        kb_doc = transform_parser_to_kblegal(parser_output, blob_path, blob_etag)
        if not kb_doc:
            logger.warning(f"[parse-tce] Mapeamento retornou vazio (sem conteúdo útil)")
            return {"status": "skipped", "reason": "no_content", "blob_path": blob_path}
        logger.info(f"[parse-tce] Mapeamento OK - chunk_id: {kb_doc.get('chunk_id', '?')}")
    except Exception as e:
        logger.error(f"[parse-tce] Erro no mapeamento: {e}")
        return {"status": "error", "error": f"mapping_failed: {e}", "blob_path": blob_path}

    # 4. Gravar JSON em stgovyparsetestsponsor/kb-raw
    try:
        main_service = _get_main_blob_service()
        raw_container = main_service.get_container_client(KB_RAW_CONTAINER)

        # Envelope com metadata para auditoria
        envelope = {
            "kb_doc": kb_doc,
            "metadata": {
                "blob_path": blob_path,
                "blob_etag": blob_etag,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "parser_version": "tce_parser_v3",
                "mapping_version": "mapping_tce_to_kblegal_v1",
            },
            "parser_raw": {
                k: v for k, v in parser_output.items()
                if k not in ("text", "text_1")  # não gravar texto bruto
            },
        }

        raw_container.get_blob_client(json_key).upload_blob(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        logger.info(f"[parse-tce] JSON gravado em kb-raw/{json_key}")
    except Exception as e:
        logger.error(f"[parse-tce] Erro gravando kb-raw: {e}")
        return {"status": "error", "error": f"save_failed: {e}", "blob_path": blob_path}

    return {
        "status": "success",
        "blob_path": blob_path,
        "json_key": json_key,
        "chunk_id": kb_doc.get("chunk_id"),
        "fields_filled": sum(1 for v in kb_doc.values() if v is not None),
    }


# ============================================================
# 3. INDEX: indexa JSON do kb-raw no Azure Search (futuro)
# ============================================================

def handle_index_kb_raw(msg_json: str) -> dict:
    """
    Indexa 1 documento do kb-raw no Azure AI Search.
    Gera embedding via OpenAI e faz upsert no índice kb-legal.

    Mensagem: { "json_key": "tce-sp--10026_989_24_acordao.json" }
    """
    # TODO: implementar quando pipeline estiver validado
    msg = json.loads(msg_json) if isinstance(msg_json, str) else msg_json
    logger.info(f"[index-kb-raw] TODO: indexar {msg.get('json_key', '?')}")
    return {"status": "not_implemented", "json_key": msg.get("json_key")}
