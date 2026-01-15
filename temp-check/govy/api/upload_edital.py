import azure.functions as func
import json

def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "stub", "message": "Upload stub"}),
        status_code=200,
        mimetype="application/json"
    )
