import azure.functions as func
import json

def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name") if body else None
    except:
        blob_name = None
    if not blob_name:
        return func.HttpResponse(
            json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
            status_code=400,
            mimetype="application/json"
        )
    return func.HttpResponse(
        json.dumps({"status": "stub_ok", "function": "extract_params", "blob_name": blob_name}),
        status_code=200,
        mimetype="application/json"
    )