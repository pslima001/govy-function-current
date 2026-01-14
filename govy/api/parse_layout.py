# govy/api/parse_layout.py
"""
Handler para parse de documentos usando Azure Document Intelligence.
"""
import json
import os
import re
import logging
from typing import Any, Dict, List

import azure.functions as func


def _json_response(status: int, payload: dict) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _clean_content(raw: str) -> str:
    if not raw:
        return ""
    text = raw.replace("\uFFFD", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = text.split("\n")
    cleaned_lines = []
    seen_short = set()
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 50:
            key = stripped.lower()
            if key in seen_short:
                continue
            seen_short.add(key)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _normalize_tables(result: Any) -> List[Dict]:
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
            })
        tables_norm.append({
            "table_index": idx,
            "row_count": table.row_count,
            "column_count": table.column_count,
            "cells": cells,
        })
    return tables_norm


def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name") if body else None
    except Exception:
        blob_name = None
    
    if not blob_name:
        return _json_response(400, {"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"})
    
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("BLOB_CONTAINER_NAME")
    di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    di_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    if not all([conn_str, container, di_endpoint, di_key]):
        return _json_response(500, {"error": "Missing environment variables"})
    
    try:
        from azure.storage.blob import BlobServiceClient
        bsc = BlobServiceClient.from_connection_string(conn_str)
        blob_client = bsc.get_blob_client(container=container, blob=blob_name)
        pdf_bytes = blob_client.download_blob().readall()
        if not pdf_bytes:
            return _json_response(404, {"error": f"Blob not found: {blob_name}"})
    except Exception as e:
        return _json_response(500, {"error": f"Erro ao baixar PDF: {str(e)}"})
    
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        
        client = DocumentIntelligenceClient(
            endpoint=di_endpoint,
            credential=AzureKeyCredential(di_key)
        )
        
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=pdf_bytes,
            content_type="application/pdf"
        )
        result = poller.result()
    except Exception as e:
        return _json_response(500, {"error": f"Erro no Document Intelligence: {str(e)}"})
    
    content_raw = result.content or ""
    content_clean = _clean_content(content_raw)
    tables_norm = _normalize_tables(result)
    page_count = len(result.pages) if hasattr(result, "pages") and result.pages else 0
    
    return _json_response(200, {
        "blob_name": blob_name,
        "content_raw": content_raw,
        "content_clean": content_clean,
        "tables_norm": tables_norm,
        "page_count": page_count,
        "tables_count": len(tables_norm),
        "content_length": len(content_clean),
    })
