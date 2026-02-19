# govy/api/get_blob_url.py
import azure.functions as func
import json
import os
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from govy.utils.azure_clients import get_blob_service_client


def handle_get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        if not blob_name:
            return func.HttpResponse(json.dumps({"error": "blob_name obrigatório"}), status_code=400, mimetype="application/json")

        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container_name, blob_name)

        user_delegation_key = blob_service.get_user_delegation_key(
            key_start_time=datetime.utcnow(),
            key_expiry_time=datetime.utcnow() + timedelta(hours=1)
        )

        sas_token = generate_blob_sas(
            account_name=os.environ.get("GOVY_STORAGE_ACCOUNT", "stgovyparsetestsponsor"),
            container_name=container_name,
            blob_name=blob_name,
            user_delegation_key=user_delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )
        url = f"{blob_client.url}?{sas_token}"
        return func.HttpResponse(json.dumps({"url": url}), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")