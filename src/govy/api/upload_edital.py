import os
import uuid
import azure.functions as func
from azure.storage.blob import BlobServiceClient, ContentSettings

def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    try:
        file = req.files.get("file")  # type: ignore[attr-defined]
    except Exception:
        file = None

    if not file:
        return func.HttpResponse(
            '{"error":"Envie multipart/form-data com campo file"}',
            status_code=400,
            mimetype="application/json",
        )

    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container = os.environ.get("BLOB_CONTAINER_NAME", "editais")
    if not conn:
        return func.HttpResponse(
            '{"error":"AZURE_STORAGE_CONNECTION_STRING não configurada"}',
            status_code=500,
            mimetype="application/json",
        )

    ext = ""
    filename = getattr(file, "filename", "") or ""
    if "." in filename:
        ext = "." + filename.split(".")[-1].lower()

    blob_name = f"uploads/{uuid.uuid4().hex}{ext}"

    bsc = BlobServiceClient.from_connection_string(conn)
    bc = bsc.get_blob_client(container=container, blob=blob_name)

    content_type = getattr(file, "content_type", None) or "application/octet-stream"
    data = file.stream.read()

    bc.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )

    return func.HttpResponse(
        f'{{"blob_name":"{blob_name}"}}',
        status_code=200,
        mimetype="application/json",
    )
