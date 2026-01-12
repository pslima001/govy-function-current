import azure.functions as func
import json

def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name") if body else None
    except:
        blob_name = None
    
    if not blob_name:
        return func.HttpResponse(
            json.dumps({"error": 'Envie JSON: {"blob_name": "uploads/arquivo.pdf"}'}),
            status_code=400,
            mimetype="application/json"
        )
    
    return func.HttpResponse(
        json.dumps({
            "status": "stub_ok",
            "function": "parse_layout",
            "blob_name": blob_name
        }),
        status_code=200,
        mimetype="application/json"
    )
