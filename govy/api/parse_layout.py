# govy/api/parse_layout.py
"""
Handler para parse de documentos usando Azure Document Intelligence.
"""
import json
import os
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

import azure.functions as func


def _json_response(status: int, payload: dict) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _clean_content(raw: str) -> str:
    """
    Remove headers/footers repetitivos e limpa o texto.
    """
    if not raw:
        return ""
    
    # Remove caracteres de substituição
    text = raw.replace("\uFFFD", "")
    
    # Normaliza espaços
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove linhas muito curtas repetidas (possíveis headers/footers)
    lines = text.split("\n")
    cleaned_lines = []
    seen_short = set()
    
    for line in lines:
        stripped = line.strip()
        # Linhas curtas repetidas são provavelmente header/footer
        if len(stripped) < 50:
            key = stripped.lower()
            if key in seen_short:
                continue
            seen_short.add(key)
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines).strip()


def _normalize_tables(result: Any) -> List[Dict]:
    """
    Normaliza tabelas do Document Intelligence para formato simplificado.
    """
    tables_norm = []
    
    if not hasattr(result, "tables") or not result.tables:
        return tables_norm
    
    for idx, table in enumerate(result.tables):
        cells = []
        for cell in table.cells:
            cells.append({
                "row": cell.row_index,
                "col": cell.column_index,
                "text": cell.content or "",
                "row_span": getattr(cell, "row_span", 1),
                "col_span": getattr(cell, "column_span", 1),
            })
        
        tables_norm.append({
            "table_index": idx,
            "row_count": table.row_count,
            "column_count": table.column_count,
            "cells": cells,
        })
    
    return tables_norm


def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/parse_layout
    
    Input: { "blob_name": "uploads/xxx.pdf" }
    
    Output: {
        "blob_name": "...",
        "content_raw": "...",
        "content_clean": "...",
        "tables_norm": [...],
        "page_count": N
    }
    """
    # 1. Validar input
    try:
        body = req.get_json()
        blob_name = body.get("blob_name") if body else None
    except Exception:
        blob_name = None
    
    if not blob_name:
        return _json_response(400, {"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"})
    
    # 2. Obter configurações do ambiente
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("BLOB_CONTAINER_NAME")
    di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    di_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    if not conn_str:
        return _json_response(500, {"error": "Missing env: AZURE_STORAGE_CONNECTION_STRING"})
    if not container:
        return _json_response(500, {"error": "Missing env: BLOB_CONTAINER_NAME"})
    if not di_endpoint:
        return _json_response(500, {"error": "Missing env: AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"})
    if not di_key:
        return _json_response(500, {"error": "Missing env: AZURE_DOCUMENT_INTELLIGENCE_KEY"})
    
    # 3. Baixar PDF do Blob Storage
    try:
        from azure.storage.blob import BlobServiceClient
        
        bsc = BlobServiceClient.from_connection_string(conn_str)
        blob_client = bsc.get_blob_client(container=container, blob=blob_name)
        pdf_bytes = blob_client.download_blob().readall()
        
        if not pdf_bytes:
            return _json_response(404, {"error": f"Blob vazio ou não encontrado: {blob_name}"})
        
        logging.info(f"PDF baixado: {blob_name}, {len(pdf_bytes)} bytes")
    except Exception as e:
        logging.exception("Erro ao baixar PDF do Blob")
        return _json_response(500, {"error": f"Erro ao baixar PDF: {str(e)}"})
    
    # 4. Enviar para Document Intelligence
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.core.credentials import AzureKeyCredential
        
        client = DocumentIntelligenceClient(
            endpoint=di_endpoint,
            credential=AzureKeyCredential(di_key)
        )
        
        poller = client.begin_analyze_document(
            model_id="prebuilt-layout",
            analyze_request=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
            content_type="application/octet-stream"
        )
        
        result = poller.result()
        
        logging.info(f"Document Intelligence concluído: {len(result.content or '')} chars")
    except Exception as e:
        logging.exception("Erro no Document Intelligence")
        return _json_response(500, {"error": f"Erro no Document Intelligence: {str(e)}"})
    
    # 5. Processar resultado
    content_raw = result.content or ""
    content_clean = _clean_content(content_raw)
    tables_norm = _normalize_tables(result)
    page_count = len(result.pages) if hasattr(result, "pages") and result.pages else 0
    
    # 6. Retornar resultado
    return _json_response(200, {
        "blob_name": blob_name,
        "content_raw": content_raw,
        "content_clean": content_clean,
        "tables_norm": tables_norm,
        "page_count": page_count,
        "tables_count": len(tables_norm),
        "content_length": len(content_clean),
    })
