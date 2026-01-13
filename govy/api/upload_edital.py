import json
import os
import uuid
from typing import Tuple
import azure.functions as func


def _json(status: int, payload: dict) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
    )


def _parse_multipart_file(req: func.HttpRequest, field_name: str = "file") -> Tuple[str, bytes]:
    """
    Extrai arquivo do multipart/form-data sem dependencias extras.
    Retorna (filename, bytes).
    """
    content_type = req.headers.get("content-type") or req.headers.get("Content-Type") or ""
    if "multipart/form-data" not in content_type.lower():
        raise ValueError("Expected multipart/form-data")

    body = req.get_body()
    if not body:
        raise ValueError("Empty request body")

    msg_bytes = b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body

    import email
    from email import policy

    msg = email.message_from_bytes(msg_bytes, policy=policy.default)

    if not msg.is_multipart():
        raise ValueError("Invalid multipart payload")

    for part in msg.iter_parts():
        cd = part.get("Content-Disposition", "") or ""
        if f'name="{field_name}"' not in cd:
            continue
        filename = part.get_filename() or "upload.pdf"
        data = part.get_payload(decode=True) or b""
        if not data:
            raise ValueError("Empty file")
        return filename, data

    raise ValueError(f"Missing multipart field: {field_name}")


def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST multipart/form-data com campo obrigatorio 'file'
    Aceita apenas PDF por enquanto.
    Salva no Blob Storage em uploads/<uuid>.pdf
    Retorna: { "blob_name": "uploads/<uuid>.pdf" }
    """
    try:
        filename, data = _parse_multipart_file(req, field_name="file")
    except Exception as e:
        return _json(400, {"error": str(e)})

    _, ext = os.path.splitext(filename or "")
    ext = (ext or "").lower()

    if ext != ".pdf":
        return _json(400, {"error": "Only PDF is accepted for now (.pdf)"})

    if not data.startswith(b"%PDF"):
        return _json(400, {"error": "File does not look like a valid PDF"})

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("BLOB_CONTAINER_NAME")

    if not conn_str:
        return _json(500, {"error": "Missing env var: AZURE_STORAGE_CONNECTION_STRING"})
    if not container:
        return _json(500, {"error": "Missing env var: BLOB_CONTAINER_NAME"})

    blob_name = f"uploads/{uuid.uuid4().hex}.pdf"

    try:
        from azure.storage.blob import BlobServiceClient
        bsc = BlobServiceClient.from_connection_string(conn_str)
        blob_client = bsc.get_blob_client(container=container, blob=blob_name)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_type="application/pdf",
        )
        return _json(200, {"blob_name": blob_name})
    except Exception as e:
        return _json(500, {"error": str(e)})
