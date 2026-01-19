# govy/api/get_blob_url.py
import azure.functions as func
import json
import os
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

def handle_get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        if not blob_name:
            return func.HttpResponse(json.dumps({"error": "blob_name obrigatório"}), status_code=400, mimetype="application/json")
        
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service.get_blob_client(container_name, blob_name)
        
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name, container_name=container_name, blob_name=blob_name,
            account_key=blob_service.credential.account_key, permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        url = f"{blob_client.url}?{sas_token}"
        return func.HttpResponse(json.dumps({"url": url}), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")