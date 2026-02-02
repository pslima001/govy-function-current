import json
import os
import uuid
import azure.functions as func
from azure.storage.blob import BlobServiceClient, ContentSettings


def handle_upload_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    """
    Upload de DOCX (capítulo/seção) para container de doutrina.
    Regras:
      - só DOCX
      - não faz LLM
    """
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        return func.HttpResponse(
            json.dumps({"error": "Missing storage connection string env var."}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    container = os.getenv("DOCTRINE_CONTAINER_NAME", "doutrina")

    try:
        file = req.files.get("file")  # type: ignore[attr-defined]
    except Exception:
        file = None

    if file is None:
        return func.HttpResponse(
            json.dumps({"error": "Envie multipart/form-data com campo 'file' (DOCX)."}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    filename = getattr(file, "filename", "") or ""
    ext = (filename.split(".")[-1] if "." in filename else "").lower()
    if ext != "docx":
        return func.HttpResponse(
            json.dumps({"error": "Arquivo inválido. Envie .docx"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    content = file.stream.read()
    if not content:
        return func.HttpResponse(
            json.dumps({"error": "Arquivo vazio."}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    blob_service = BlobServiceClient.from_connection_string(conn)
    cont = blob_service.get_container_client(container)

    blob_name = f"raw/{uuid.uuid4().hex}.docx"
    bc = cont.get_blob_client(blob_name)

    bc.upload_blob(
        content,
        overwrite=True,
        content_settings=ContentSettings(
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    return func.HttpResponse(
        json.dumps({"container": container, "blob_name": blob_name}, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
