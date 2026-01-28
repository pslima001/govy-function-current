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
