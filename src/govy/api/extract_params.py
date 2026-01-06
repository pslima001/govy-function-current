import json
import azure.functions as func

from govy.api.parse_layout import handle_parse_layout
from govy.run.extract_all import extract_all_params


def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handler para POST /api/extract_params
    Espera JSON: {"blob_name": "...", "include_debug": false}
    """

    try:
        body = req.get_json()
        include_debug = bool(body.get("include_debug", False))
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Envie JSON válido"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    # Reusa parse_layout para obter content_clean + tables_norm
    parse_resp = handle_parse_layout(req)
    if parse_resp.status_code != 200:
        return parse_resp

    try:
        payload = json.loads(parse_resp.get_body().decode("utf-8"))
        content_clean = payload.get("content_clean", "") or ""
        tables_norm = payload.get("tables_norm", []) or []
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": f"Falha ao ler payload do parse_layout: {str(e)}"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    params = extract_all_params(content_clean=content_clean, tables_norm=tables_norm, include_debug=include_debug)

    out = {
        "blob_name": payload.get("blob_name"),
        "params": params,
        "content_clean": content_clean,
        "tables_norm": tables_norm,
    }

    return func.HttpResponse(
        json.dumps(out, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
