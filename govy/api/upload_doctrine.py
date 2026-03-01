import json
import os
import uuid
import traceback
import azure.functions as func
from azure.storage.blob import ContentSettings
from govy.utils.azure_clients import get_blob_service_client


def handle_upload_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    """
    Upload de DOCX (capítulo/seção) para container de doutrina.
    Regras:
      - só DOCX
      - não faz LLM
    """
    try:
        container = os.getenv("DOCTRINE_CONTAINER_NAME", "kb-doutrina-raw")

        # Azure Functions (python) expõe req.files quando multipart/form-data
        try:
            file = req.files.get("file")  # type: ignore[attr-defined]
        except Exception as e:
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "req.files not available or failed to parse multipart/form-data",
                        "details": str(e),
                        "hint": "Your runtime may not support req.files. We'll switch to base64 JSON upload if needed.",
                    },
                    ensure_ascii=False,
                ),
                status_code=400,
                mimetype="application/json",
            )

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
                json.dumps({"error": "Arquivo inválido. Envie .docx", "received_filename": filename}, ensure_ascii=False),
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
                {"error": "Unhandled exception in upload_doctrine", "details": str(e), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            status_code=500,
            mimetype="application/json",
        )
