# function_app.py
"""
Azure Functions - Govy Backend
Registro das funções HTTP
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

# Consult LLMs (NOVO)
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
