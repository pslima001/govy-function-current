# govy/api/parse_layout.py
"""
Handler para parsing de layout via Azure Document Intelligence.

Última atualização: 15/01/2026
CORRIGIDO: Parâmetro 'body' ao invés de 'analyze_request' (SDK v1.0+)
"""
import os
import json
import logging

import azure.functions as func

logger = logging.getLogger(__name__)


def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    """
    Faz parsing do layout de um PDF usando Azure Document Intelligence.

    Espera JSON: {"blob_name": "uploads/xxx.pdf"}

    Returns:
        JSON com texto extraído e tabelas normalizadas
    """
    try:
        # Obtém blob_name do body
        try:
            body = req.get_json()
            blob_name = body.get("blob_name") if body else None
        except Exception:
            blob_name = None

        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
                status_code=400,
                mimetype="application/json"
            )

        # Importa aqui para evitar erro no startup
        from azure.storage.blob import BlobServiceClient
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        # Configurações
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        di_endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        di_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")

        if not conn_str:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING não configurada"}),
                status_code=500,
                mimetype="application/json"
            )

        if not di_endpoint or not di_key:
            return func.HttpResponse(
                json.dumps({"error": "Document Intelligence não configurado (AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT/KEY)"}),
                status_code=500,
                mimetype="application/json"
            )

        # Baixa o PDF do Blob Storage
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)

        try:
            pdf_bytes = blob_client.download_blob().readall()
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": f"Blob não encontrado: {blob_name}", "details": str(e)}),
                status_code=404,
                mimetype="application/json"
            )

        logger.info(f"PDF baixado: {blob_name} ({len(pdf_bytes)} bytes)")

        # Analisa com Document Intelligence
        di_client = DocumentIntelligenceClient(
            endpoint=di_endpoint,
            credential=AzureKeyCredential(di_key)
        )

        # 🔧 CORREÇÃO: Usar 'body' ao invés de 'analyze_request'
        poller = di_client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=pdf_bytes,  # ✅ CORRIGIDO
            content_type="application/pdf"
        )

        result = poller.result()

        # Extrai texto completo
        texto_completo = result.content if hasattr(result, "content") else ""

        # Normaliza tabelas
        tables_norm = []
        if hasattr(result, "tables") and result.tables:
            for idx, table in enumerate(result.tables):
                cells_data = []
                if hasattr(table, "cells") and table.cells:
                    for cell in table.cells:
                        cells_data.append({
                            "row": cell.row_index if hasattr(cell, "row_index") else 0,
                            "col": cell.column_index if hasattr(cell, "column_index") else 0,
                            "text": cell.content if hasattr(cell, "content") else "",
                        })

                tables_norm.append({
                    "table_index": idx,
                    "row_count": table.row_count if hasattr(table, "row_count") else 0,
                    "column_count": table.column_count if hasattr(table, "column_count") else 0,
                    "cells": cells_data
                })

        logger.info(f"Parse OK: {len(texto_completo)} chars, {len(tables_norm)} tabelas")

        # Salva resultado como JSON no blob storage (para uso posterior)
        result_blob_name = blob_name.replace(".pdf", "_parsed.json")
        result_data = {
            "blob_name": blob_name,
            "texto_completo": texto_completo,
            "tables_norm": tables_norm,
            "page_count": len(result.pages) if hasattr(result, "pages") and result.pages else 0
        }

        result_blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=result_blob_name
        )
        result_blob_client.upload_blob(
            json.dumps(result_data, ensure_ascii=False),
            overwrite=True
        )

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "parsed_blob": result_blob_name,
                "text_length": len(texto_completo),
                "tables_count": len(tables_norm),
                "page_count": result_data["page_count"]
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.exception("Erro no parse_layout")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )