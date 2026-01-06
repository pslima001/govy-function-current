import json
import os
from typing import Any, Dict, List

import azure.functions as func


def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handler para POST /api/parse_layout
    Espera JSON: {"blob_name": "..."}
    Retorna: content_raw, content_clean, tables_norm
    """

    # Imports pesados ficam aqui dentro (para não quebrar indexing)
    from azure.storage.blob import BlobServiceClient
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    # 1) Ler input
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name é obrigatório"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    # 2) Baixar PDF do Blob
    try:
        conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        container = os.environ["BLOB_CONTAINER_NAME"]

        bsc = BlobServiceClient.from_connection_string(conn_str)
        blob = bsc.get_blob_client(container=container, blob=blob_name)
        pdf_bytes = blob.download_blob().readall()
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Falha ao baixar blob: {str(e)}"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    # 3) Chamar Document Intelligence
    try:
        endpoint = os.environ["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
        key = os.environ["AZURE_DOCUMENT_INTELLIGENCE_KEY"]

        client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        poller = client.begin_analyze_document("prebuilt-layout", pdf_bytes)
        result = poller.result()
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Falha no Document Intelligence: {str(e)}"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    # 4) Tabelas normalizadas
    tables: List[Dict[str, Any]] = []
    try:
        for t_idx, table in enumerate(result.tables or []):
            cells = []
            for cell in table.cells:
                cells.append(
                    {"row": cell.row_index, "col": cell.column_index, "text": (cell.content or "").strip()}
                )
            tables.append(
                {
                    "table_index": t_idx,
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": cells,
                }
            )
    except Exception:
        tables = []

    payload = {
        "blob_name": blob_name,
        "content_raw": (result.content or ""),
        "content_clean": (result.content or "").strip(),
        "tables_norm": tables,
    }

    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
