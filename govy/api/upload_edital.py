# govy/api/upload_edital.py
"""
Handler para upload de editais PDF.

Última atualização: 16/01/2026
MODIFICADO: Usa hash MD5 do conteúdo como identificador único
           - Mesmo PDF = mesmo blob_name = encontra cache do parse
"""
import os
import json
import hashlib
import logging
import azure.functions as func

logger = logging.getLogger(__name__)


def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    """
    Faz upload de um arquivo PDF para o Azure Blob Storage.
    
    Usa hash MD5 do conteúdo como nome do blob, garantindo que:
    - Mesmo arquivo = mesmo blob_name
    - Parse existente será encontrado no cache
    
    Espera multipart/form-data com campo 'file' contendo o PDF.
    
    Returns:
        JSON com blob_name do arquivo salvo
    """
    try:
        # Importa aqui para evitar erro no startup se variáveis não existirem
        from govy.utils.azure_clients import get_blob_service_client

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

        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")

        # ================================================================
        # GERA NOME ÚNICO BASEADO NO HASH MD5 DO CONTEÚDO
        # ================================================================
        content_hash = hashlib.md5(content).hexdigest()
        blob_name = f"uploads/{content_hash}.pdf"

        # Conecta ao Blob Storage
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)

        # Verifica se o arquivo já existe
        already_exists = False
        try:
            blob_client.get_blob_properties()
            already_exists = True
        except Exception:
            pass

        # Upload (só faz se não existir, ou sobrescreve se existir)
        blob_client.upload_blob(content, overwrite=True)

        logger.info(f"Upload OK: {blob_name} ({len(content)} bytes) - exists={already_exists}")

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "size_bytes": len(content),
                "original_filename": filename,
                "content_hash": content_hash,
                "already_existed": already_exists
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
