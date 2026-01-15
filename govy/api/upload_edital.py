# govy/api/upload_edital.py
"""
Handler para upload de editais PDF.

Última atualização: 15/01/2026
"""
import os
import json
import uuid
import logging

import azure.functions as func

logger = logging.getLogger(__name__)


def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    """
    Faz upload de um arquivo PDF para o Azure Blob Storage.
    
    Espera multipart/form-data com campo 'file' contendo o PDF.
    
    Returns:
        JSON com blob_name do arquivo salvo
    """
    try:
        # Importa aqui para evitar erro no startup se variáveis não existirem
        from azure.storage.blob import BlobServiceClient
        
        # Obtém arquivo do request
        file = req.files.get("file")
        if not file:
            return func.HttpResponse(
                json.dumps({"error": "Campo 'file' não encontrado no form-data"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Valida extensão
        filename = file.filename or "documento.pdf"
        if not filename.lower().endswith(".pdf"):
            return func.HttpResponse(
                json.dumps({"error": "Apenas arquivos PDF são aceitos"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Lê conteúdo
        content = file.read()
        if not content:
            return func.HttpResponse(
                json.dumps({"error": "Arquivo vazio"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Conecta ao Blob Storage
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING não configurada"}),
                status_code=500,
                mimetype="application/json"
            )
        
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        
        # Gera nome único
        unique_id = uuid.uuid4().hex
        blob_name = f"uploads/{unique_id}.pdf"
        
        # Upload
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
        blob_client.upload_blob(content, overwrite=True)
        
        logger.info(f"Upload OK: {blob_name} ({len(content)} bytes)")
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "size_bytes": len(content),
                "original_filename": filename
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro no upload_edital")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
