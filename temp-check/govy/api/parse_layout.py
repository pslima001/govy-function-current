import azure.functions as func
import json

def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "stub", "message": "Parse layout stub"}),
        status_code=200,
        mimetype="application/json"
    )
