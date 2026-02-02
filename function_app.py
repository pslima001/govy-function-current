# function_app.py
"""
Azure Functions - Govy Backend
Registro das funcoes HTTP
"""
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Ping
@app.route(route="ping", methods=["GET"])
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)

# Diag
@app.route(route="diag", methods=["GET"])
def diag(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.diag import handle_diag
    return handle_diag(req)

# Upload Edital
@app.route(route="upload_edital", methods=["POST"])
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_edital import handle_upload_edital
    return handle_upload_edital(req)

# Parse Layout
@app.route(route="parse_layout", methods=["POST"])
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.parse_layout import handle_parse_layout
    return handle_parse_layout(req)

# Extract Params
@app.route(route="extract_params", methods=["POST"])
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params import handle_extract_params
    return handle_extract_params(req)

# Get Blob URL
@app.route(route="get_blob_url", methods=["POST"])
def get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.get_blob_url import handle_get_blob_url
    return handle_get_blob_url(req)

# Consult LLMs
@app.route(route="consult_llms", methods=["POST"])
def consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.consult_llms import handle_consult_llms
    return handle_consult_llms(req)

# Extract Params Amplos
@app.route(route="extract_params_amplos", methods=["POST"])
def extract_params_amplos(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params_amplos import handle_extract_params_amplos
    return handle_extract_params_amplos(req)

# Extract Items
@app.route(route="extract_items", methods=["POST"])
def extract_items(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_items import handle_extract_items
    return handle_extract_items(req)

# Dicionario API
@app.route(route="dicionario", methods=["GET", "POST", "DELETE"])
def dicionario(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.dicionario_api import handle_dicionario
    return handle_dicionario(req)

# ============================================================
# DOUTRINA ENDPOINTS (Habilitação - primeira doutrina)
# ============================================================

@app.function_name(name="upload_doctrine")
@app.route(route="upload_doctrine", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_doctrine import handle_upload_doctrine
    return handle_upload_doctrine(req)


@app.function_name(name="ingest_doctrine")
@app.route(route="ingest_doctrine", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.ingest_doctrine import handle_ingest_doctrine
    return handle_ingest_doctrine(req)

@app.function_name(name="upload_doctrine_b64")
@app.route(route="upload_doctrine_b64", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_doctrine_b64(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_doctrine_b64 import handle_upload_doctrine_b64
    return handle_upload_doctrine_b64(req)


# ============================================================
# JURISPRUDENCIA ENDPOINTS
# ============================================================

# Juris Upload
@app.route(route="juris/upload", methods=["POST"])
def api_juris_upload(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_upload import main
    return main(req)

# Juris Fichas
@app.route(route="juris/fichas", methods=["GET"])
def api_juris_fichas(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_fichas import main
    return main(req)

# Juris Validar
@app.route(route="juris/validar", methods=["POST"])
def api_juris_validar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_validar import main
    return main(req)

# Juris Buscar
@app.route(route="juris/buscar", methods=["POST"])
def api_juris_buscar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_buscar import main
    return main(req)

# KB Index Upsert
@app.route(route="kb/index/upsert", methods=["POST", "OPTIONS"])
def kb_index_upsert(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_index_upsert import main
    return main(req)

# KB Search
@app.route(route="kb/search", methods=["POST", "OPTIONS"])
def kb_search(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_search import main
    return main(req)

# KB Effect Classify (2-pass: GPT-4o + Claude Sonnet)
@app.route(route="kb/effect/classify", methods=["POST", "OPTIONS"])
def kb_effect_classify(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_effect_classify import main
    return main(req)

# =============================================================================
# KB JURIS EXTRACT - SPEC 1.2
# =============================================================================

# KB Juris Extract All (pipeline completo)
@app.route(route="kb/juris/extract_all", methods=["POST", "OPTIONS"])
def kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import main
    return main(req)

# KB Juris Review Queue - Listar pendentes
@app.route(route="kb/juris/review_queue", methods=["GET"])
def kb_juris_review_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_review_queue
    return list_review_queue(req)

# KB Juris Review Queue - Obter item
@app.route(route="kb/juris/review_queue/{item_id}", methods=["GET"])
def kb_juris_review_get(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_review_item
    return get_review_item(req)

# KB Juris Review Queue - Aprovar item
@app.route(route="kb/juris/review_queue/{item_id}/approve", methods=["POST"])
def kb_juris_review_approve(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import approve_review_item
    return approve_review_item(req)

# KB Juris Review Queue - Rejeitar item
@app.route(route="kb/juris/review_queue/{item_id}/reject", methods=["POST"])
def kb_juris_review_reject(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import reject_review_item
    return reject_review_item(req)

# ==============================================================================
# KB JURIS - LISTS & STATS
# ==============================================================================

@app.function_name(name="kb_juris_approved_list")
@app.route(route="kb/juris/approved", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_approved_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_approved_items
    return list_approved_items(req)

@app.function_name(name="kb_juris_blocked_list")
@app.route(route="kb/juris/blocked", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_blocked_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_blocked_items
    return list_blocked_items(req)

@app.function_name(name="kb_juris_rejected_list")
@app.route(route="kb/juris/rejected", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_rejected_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_rejected_items
    return list_rejected_items(req)

@app.function_name(name="kb_juris_stats")
@app.route(route="kb/juris/stats", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_stats(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_queue_stats
    return get_queue_stats(req)
