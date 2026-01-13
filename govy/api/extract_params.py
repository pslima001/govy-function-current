# govy/api/extract_params.py
"""
Handler para extração de parâmetros de editais.
"""
import json
import os
import re
import logging
from typing import Any, Dict

import azure.functions as func


def _json_response(status: int, payload: dict) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _download_pdf(blob_name: str) -> bytes:
    """Baixa PDF do Blob Storage."""
    from azure.storage.blob import BlobServiceClient
    
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("BLOB_CONTAINER_NAME")
    
    bsc = BlobServiceClient.from_connection_string(conn_str)
    blob_client = bsc.get_blob_client(container=container, blob=blob_name)
    return blob_client.download_blob().readall()


def _parse_document(pdf_bytes: bytes) -> Dict[str, Any]:
    """Executa Document Intelligence no PDF."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
    
    di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    di_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    client = DocumentIntelligenceClient(
        endpoint=di_endpoint,
        credential=AzureKeyCredential(di_key)
    )
    
    # API correta para azure-ai-documentintelligence >= 1.0.0
    poller = client.begin_analyze_document(
        "prebuilt-layout",
        body=pdf_bytes,
        content_type="application/pdf"
    )
    
    result = poller.result()
    
    # Extrair conteúdo limpo
    content_raw = result.content or ""
    content_clean = content_raw.replace("\uFFFD", "")
    content_clean = re.sub(r"[ \t]+", " ", content_clean)
    content_clean = re.sub(r"\n{3,}", "\n\n", content_clean)
    
    # Normalizar tabelas
    tables_norm = []
    if hasattr(result, "tables") and result.tables:
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
    
    return {
        "content_clean": content_clean,
        "tables_norm": tables_norm,
        "page_count": len(result.pages) if hasattr(result, "pages") and result.pages else 0,
    }


def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/extract_params
    Input: { "blob_name": "uploads/xxx.pdf" }
    """
    try:
        body = req.get_json()
        blob_name = body.get("blob_name") if body else None
    except Exception:
        blob_name = None
    
    if not blob_name:
        return _json_response(400, {"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"})
    
    required_vars = [
        "AZURE_STORAGE_CONNECTION_STRING",
        "BLOB_CONTAINER_NAME", 
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "AZURE_DOCUMENT_INTELLIGENCE_KEY"
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            return _json_response(500, {"error": f"Missing env: {var}"})
    
    # Baixar PDF
    try:
        pdf_bytes = _download_pdf(blob_name)
        if not pdf_bytes:
            return _json_response(404, {"error": f"Blob not found: {blob_name}"})
    except Exception as e:
        return _json_response(500, {"error": f"Erro ao baixar PDF: {str(e)}"})
    
    # Parsear documento
    try:
        parsed = _parse_document(pdf_bytes)
    except Exception as e:
        return _json_response(500, {"error": f"Erro no parse: {str(e)}"})
    
    # Extrair parâmetros
    try:
        from govy.run.extract_all import extract_all_params
        
        params = extract_all_params(
            content_clean=parsed["content_clean"],
            tables_norm=parsed["tables_norm"],
            include_debug=True
        )
        
        found_count = sum(1 for p in params.values() if isinstance(p, dict) and p.get("status") == "found")
    except Exception as e:
        return _json_response(500, {"error": f"Erro na extração: {str(e)}"})
    
    return _json_response(200, {
        "blob_name": blob_name,
        "params": params,
        "meta": {
            "content_length": len(parsed["content_clean"]),
            "tables_count": len(parsed["tables_norm"]),
            "page_count": parsed["page_count"],
            "found_count": found_count,
        }
    })
