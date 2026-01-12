import azure.functions as func
import json

def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "stub_ok", "function": "upload_edital"}),
        status_code=200,
        mimetype="application/json"
    )