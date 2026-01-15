· PY
Copiar

# govy/api/parse_layout.py
"""
Handler para parsing de layout de PDFs via Azure Document Intelligence.

🆕 ATUALIZAÇÃO 15/01/2026: Sistema de cache para economizar custos
- Verifica se _parsed.json já existe antes de chamar Document Intelligence
- Usa parâmetro force_parse=true para forçar re-processamento
- Economia de ~99% em testes repetidos do mesmo PDF

Última atualização: 15/01/2026
"""
import os
import json
import logging
from datetime import datetime

import azure.functions as func

logger = logging.getLogger(__name__)


def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    """
    Faz parsing do layout de um PDF usando Azure Document Intelligence.
    
    🆕 CACHE: Se o PDF já foi parseado, retorna o cache existente.
    Use force_parse=true para forçar re-processamento.
    
    Espera JSON: 
    {
        "blob_name": "uploads/xxx.pdf",
        "force_parse": false  // opcional, default false
    }
    
    Returns:
        JSON com texto extraído e tabelas normalizadas
    """
    try:
        # =================================================================
        # 1. VALIDAÇÃO DO REQUEST
        # =================================================================
        try:
            body = req.get_json()
            blob_name = body.get("blob_name") if body else None
            force_parse = body.get("force_parse", False) if body else False
        except Exception:
            blob_name = None
            force_parse = False
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # =================================================================
        # 2. IMPORTAÇÕES (dentro da função para evitar erro no startup)
        # =================================================================
        from azure.storage.blob import BlobServiceClient
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.core.credentials import AzureKeyCredential
        
        # =================================================================
        # 3. CONFIGURAÇÕES
        # =================================================================
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
        
        # =================================================================
        # 4. CONECTAR AO BLOB STORAGE
        # =================================================================
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        
        # Nome do arquivo de cache
        parsed_blob_name = blob_name.replace(".pdf", "_parsed.json")
        
        # =================================================================
        # 🆕 5. VERIFICAR CACHE EXISTENTE
        # =================================================================
        if not force_parse:
            try:
                cache_blob_client = blob_service.get_blob_client(
                    container=container_name, 
                    blob=parsed_blob_name
                )
                
                # Tenta baixar o cache
                cache_data = json.loads(cache_blob_client.download_blob().readall())
                
                # Cache encontrado! Retornar sem chamar Document Intelligence
                logger.info(f"✅ CACHE HIT: {parsed_blob_name} - Economia de custo!")
                
                return func.HttpResponse(
                    json.dumps({
                        "status": "success",
                        "source": "cache",  # 🆕 Indica que veio do cache
                        "blob_name": blob_name,
                        "parsed_blob": parsed_blob_name,
                        "text_length": len(cache_data.get("texto_completo", "")),
                        "tables_count": len(cache_data.get("tables_norm", [])),
                        "page_count": cache_data.get("page_count", 0),
                        "cached_at": cache_data.get("parsed_at", "unknown"),
                        "message": "Parse recuperado do cache. Use force_parse=true para re-processar."
                    }),
                    status_code=200,
                    mimetype="application/json"
                )
                
            except Exception as cache_error:
                # Cache não existe ou erro ao ler - continuar com processamento normal
                logger.info(f"📥 CACHE MISS: {parsed_blob_name} - Processando com Document Intelligence...")
        else:
            logger.info(f"🔄 FORCE PARSE: Ignorando cache por solicitação do usuário")
        
        # =================================================================
        # 6. BAIXAR PDF DO BLOB STORAGE
        # =================================================================
        blob_client = blob_service.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        try:
            pdf_bytes = blob_client.download_blob().readall()
            logger.info(f"PDF baixado: {blob_name} ({len(pdf_bytes)} bytes)")
        except Exception as e:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Erro ao baixar PDF: {blob_name}",
                    "details": str(e)
                }),
                status_code=404,
                mimetype="application/json"
            )
        
        # =================================================================
        # 7. PROCESSAR COM DOCUMENT INTELLIGENCE
        # =================================================================
        client = DocumentIntelligenceClient(
            endpoint=di_endpoint,
            credential=AzureKeyCredential(di_key)
        )
        
        logger.info(f"Iniciando análise com Document Intelligence...")
        
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            analyze_request=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
            content_type="application/octet-stream"
        )
        result = poller.result()
        
        logger.info(f"Análise concluída. Processando resultado...")
        
        # =================================================================
        # 8. EXTRAIR TEXTO COMPLETO
        # =================================================================
        texto_completo = result.content if hasattr(result, "content") else ""
        
        # =================================================================
        # 9. NORMALIZAR TABELAS
        # =================================================================
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
                            "row_span": cell.row_span if hasattr(cell, "row_span") else 1,
                            "col_span": cell.column_span if hasattr(cell, "column_span") else 1
                        })
                
                tables_norm.append({
                    "table_index": idx,
                    "row_count": table.row_count if hasattr(table, "row_count") else 0,
                    "col_count": table.column_count if hasattr(table, "column_count") else 0,
                    "cells": cells_data
                })
        
        page_count = len(result.pages) if hasattr(result, "pages") and result.pages else 0
        
        logger.info(f"Parse OK: {len(texto_completo)} chars, {len(tables_norm)} tabelas, {page_count} páginas")
        
        # =================================================================
        # 10. SALVAR RESULTADO NO BLOB STORAGE (CACHE)
        # =================================================================
        result_data = {
            "blob_name": blob_name,
            "texto_completo": texto_completo,
            "tables_norm": tables_norm,
            "page_count": page_count,
            "parsed_at": datetime.utcnow().isoformat() + "Z"  # 🆕 Timestamp do parse
        }
        
        result_blob_client = blob_service.get_blob_client(
            container=container_name, 
            blob=parsed_blob_name
        )
        result_blob_client.upload_blob(
            json.dumps(result_data, ensure_ascii=False),
            overwrite=True
        )
        
        logger.info(f"✅ Cache salvo: {parsed_blob_name}")
        
        # =================================================================
        # 11. RETORNAR RESPOSTA
        # =================================================================
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "source": "document_intelligence",  # 🆕 Indica que processou agora
                "blob_name": blob_name,
                "parsed_blob": parsed_blob_name,
                "text_length": len(texto_completo),
                "tables_count": len(tables_norm),
                "page_count": page_count,
                "parsed_at": result_data["parsed_at"]
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