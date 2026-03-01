import base64
import json
import os
import uuid
import traceback
import azure.functions as func
from azure.storage.blob import ContentSettings
from govy.utils.azure_clients import get_blob_service_client


def handle_upload_doctrine_b64(req: func.HttpRequest) -> func.HttpResponse:
    """
    Upload de doutrina via JSON (base64) para evitar multipart/form-data.

    Body:
    {
      "filename": "habilitacao.docx",
      "file_b64": "<base64>"
    }
    """
    try:
        data = req.get_json()
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Envie JSON válido com filename e file_b64."}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    try:
        filename = str(data.get("filename") or "")
        file_b64 = str(data.get("file_b64") or "")

        if not filename or not file_b64:
            return func.HttpResponse(
                json.dumps({"error": "Campos obrigatórios: filename, file_b64"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        ext = (filename.split(".")[-1] if "." in filename else "").lower()
        if ext != "docx":
            return func.HttpResponse(
                json.dumps({"error": "Arquivo inválido. Envie .docx", "received_filename": filename}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        try:
            content = base64.b64decode(file_b64, validate=True)
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": "file_b64 inválido", "details": str(e)}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        if not content:
            return func.HttpResponse(
                json.dumps({"error": "Arquivo vazio após decode base64."}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        container = os.getenv("DOCTRINE_CONTAINER_NAME", "kb-doutrina-raw")

        blob_service = get_blob_service_client()
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

    except Exception as e:
        return func.HttpResponse(
            json.dumps(
                {"error": "Unhandled exception in upload_doctrine_b64", "details": str(e), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            status_code=500,
            mimetype="application/json",
        )
