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
    # Usa o prefix real (ex: "tce-sp/relatorios_voto/") para gerar kb_prefix mais específico,
    # evitando listar todos os JSONs do tribunal (ex: acordaos + relatorios_voto juntos).
    existing_keys = set()
    if skip_existing:
        try:
            kb_prefix = prefix.replace("/", "--")
            for blob in raw_container.list_blobs(name_starts_with=kb_prefix):
                existing_keys.add(blob.name)
        except Exception as e:
            logger.warning(f"Erro listando kb-raw: {e}")

    messages = []
    skipped = 0

    for blob in source_container.list_blobs(name_starts_with=prefix):
        if not blob.name.lower().endswith(".pdf"):
            continue
        if blob.name.lower().endswith(".voto.pdf"):
            continue
        if blob.name.lower().endswith("_relatorio.pdf"):
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


def _normalize_scraper_fields(meta: dict) -> dict:
    """Normaliza campos do scraper JSON para nomes esperados pelo merge.

    Suporta formatos de vários scrapers:
    - Genérico: numero_processo, data_decisao, relator, colegiado, ...
    - TCE-RS: nr_processo_fmt, dt_sessao, magistrado, orgao_julgador, ...
    """
    norm = {}
    # processo
    if meta.get("numero_processo"):
        norm["processo"] = meta["numero_processo"]
    elif meta.get("nr_processo_fmt"):
        norm["processo"] = meta["nr_processo_fmt"]
    # acordao_numero
    if meta.get("numero_acordao"):
        norm["acordao_numero"] = meta["numero_acordao"]
    # julgamento_date
    if meta.get("data_decisao"):
        norm["julgamento_date"] = meta["data_decisao"]
    elif meta.get("dt_sessao"):
        # ISO datetime → DD/MM/YYYY
        dt_raw = meta["dt_sessao"]
        if isinstance(dt_raw, str) and len(dt_raw) >= 10:
            try:
                from datetime import datetime as _dt
                parsed = _dt.fromisoformat(dt_raw.replace("Z", "+00:00"))
                norm["julgamento_date"] = parsed.strftime("%d/%m/%Y")
            except Exception:
                norm["julgamento_date"] = dt_raw[:10]
    # publication_date
    if meta.get("data_publicacao"):
        norm["publication_date"] = meta["data_publicacao"]
    elif meta.get("publicacao_dt"):
        dt_raw = meta["publicacao_dt"]
        if isinstance(dt_raw, str) and len(dt_raw) >= 10:
            try:
                from datetime import datetime as _dt
                parsed = _dt.fromisoformat(dt_raw.replace("Z", "+00:00"))
                norm["publication_date"] = parsed.strftime("%d/%m/%Y")
            except Exception:
                norm["publication_date"] = dt_raw[:10]
    # relator
    if meta.get("relator"):
        norm["relator"] = meta["relator"]
    elif meta.get("magistrado"):
        norm["relator"] = meta["magistrado"]
    # orgao_julgador
    if meta.get("colegiado"):
        norm["orgao_julgador"] = meta["colegiado"]
    elif meta.get("orgao_julgador"):
        norm["orgao_julgador"] = meta["orgao_julgador"]
    # ementa
    if meta.get("ementa_full"):
        norm["ementa"] = meta["ementa_full"]
    elif meta.get("texto_ementa"):
        norm["ementa"] = meta["texto_ementa"]
    # tipo_processo
    if meta.get("tipo_processo"):
        norm["tipo_processo"] = meta["tipo_processo"]
    # source_url
    if meta.get("link_detalhes"):
        norm["source_url"] = meta["link_detalhes"]
    elif meta.get("link_decisao"):
        norm["source_url"] = meta["link_decisao"]
    return norm


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
    #    include_text=True quando text_strategy="full_text" (PDFs curtos sem seções padrão)
    _include_text = cfg.text_strategy == "full_text"
    try:
        parser_output = parse_pdf_bytes(pdf_bytes, include_text=_include_text)
        logger.info(f"[parse-tce] Parser OK - {sum(1 for v in parser_output.values() if v != '__MISSING__' and v != [])}/25 campos")
    except Exception as e:
        logger.error(f"[parse-tce] Erro no parser: {e}")
        return {"status": "error", "error": f"parse_failed: {e}", "blob_path": blob_path}

    # 2a. Pre-filter: detect non-decision attachments (tables, maps, appendices)
    #     If parser found zero structured legal content, check raw text for markers.
    #     Saves cost of scraper-metadata fetch + mapping + blob write.
    _MISSING = "__MISSING__"
    _LEGAL_MARKERS = ("EMENTA", "DISPOSITIVO", "ACORDAM", "ACÓRDÃO",
                      "RELATÓRIO", "VOTO", "DECIDE",
                      "TRIBUNAL DE CONTAS", "DECISÃO N.")
    _em = parser_output.get("ementa", _MISSING)
    _di = parser_output.get("dispositivo", _MISSING)
    _kc = parser_output.get("key_citation", _MISSING)
    if _em == _MISSING and _di == _MISSING and _kc == _MISSING:
        try:
            import fitz
            _doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            _raw = "".join(p.get_text() for p in _doc).upper()
            _doc.close()
            if not any(m in _raw for m in _LEGAL_MARKERS):
                logger.info(f"[parse-tce] Pre-filter: no legal markers in {blob_path} "
                            f"({len(_raw)}c), skipping as non-decision attachment")
                return {
                    "status": "terminal_skip",
                    "reason": "non_decision_attachment",
                    "blob_path": blob_path,
                    "text_length": len(_raw),
                }
        except Exception:
            pass  # if check fails, continue normal flow

    # 2b. Ler metadata do scraper (se existir)
    scraper_meta = None
    try:
        meta_blob_path = blob_path.rsplit(".", 1)[0] + ".json"
        meta_bytes = source.get_blob_client(meta_blob_path).download_blob().readall()
        scraper_meta = json.loads(meta_bytes)
        logger.info(f"[parse-tce] Scraper metadata: {meta_blob_path}")
    except Exception:
        logger.debug(f"[parse-tce] Sem scraper metadata para {blob_path}")

    # 2c. Merge scraper → parser (scraper priority para processo/datas/relator)
    if scraper_meta:
        from govy.api.tce_parser_v3 import merge_with_scraper_metadata
        parser_output = merge_with_scraper_metadata(
            parser_output, _normalize_scraper_fields(scraper_meta)
        )

    # 2d. Override tribunal fields from config (parser detects from text,
    #     may misidentify when doc cites other courts e.g. TCU citing STF)
    if tribunal_id == "tcu":
        parser_output["tribunal_type"] = "TCU"
        parser_output["tribunal_name"] = "TRIBUNAL DE CONTAS DA UNIAO"
        parser_output["uf"] = "__MISSING__"
        parser_output["region"] = "__MISSING__"
    elif tribunal_id.startswith("tce-") and cfg.uf:
        parser_output["tribunal_type"] = "TCE"
        detected_name = parser_output.get("tribunal_name", "").upper()
        # Corrigir se parser detectou tribunal errado (STF, STJ, TCU, ou outro TCE)
        if not detected_name.startswith("TRIBUNAL DE CONTAS DO ESTADO") and \
           not detected_name.startswith(f"TCE-{cfg.uf}") and \
           not detected_name.startswith(f"TCE {cfg.uf}"):
            parser_output["tribunal_name"] = cfg.display_name
        parser_output["uf"] = cfg.uf
    elif tribunal_id.startswith("tcm-") and cfg.uf:
        parser_output["tribunal_type"] = "TCM"
        detected_name = parser_output.get("tribunal_name", "").upper()
        # Corrigir se parser detectou tribunal errado (STF, STJ, TCU, TCE, etc.)
        if not detected_name.startswith("TRIBUNAL DE CONTAS DO MUNICIPIO") and \
           not detected_name.startswith(f"TCM-{cfg.uf}") and \
           not detected_name.startswith(f"TCM {cfg.uf}"):
            parser_output["tribunal_name"] = cfg.display_name
        parser_output["uf"] = cfg.uf

    # 3. Mapear para kb-legal
    try:
        kb_doc = transform_parser_to_kblegal(parser_output, blob_path, blob_etag, config=cfg)
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
