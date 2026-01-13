import sys
import os
import logging

import azure.functions as func

# Adiciona o diretório raiz ao path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = func.FunctionApp()

# Diagnóstico detalhado
_diag_info = []
_diag_info.append(f"ROOT: {ROOT}")
_diag_info.append(f"sys.path: {sys.path[:5]}")
_diag_info.append(f"Contents of ROOT: {os.listdir(ROOT) if os.path.exists(ROOT) else 'NOT FOUND'}")

govy_path = os.path.join(ROOT, "govy")
_diag_info.append(f"govy exists: {os.path.exists(govy_path)}")
if os.path.exists(govy_path):
    _diag_info.append(f"govy contents: {os.listdir(govy_path)}")

api_path = os.path.join(ROOT, "govy", "api")
_diag_info.append(f"govy/api exists: {os.path.exists(api_path)}")
if os.path.exists(api_path):
    _diag_info.append(f"govy/api contents: {os.listdir(api_path)}")

_import_err = None
try:
    from govy.api.upload_edital import handle_upload_edital
    from govy.api.parse_layout import handle_parse_layout
    from govy.api.extract_params import handle_extract_params
    _diag_info.append("IMPORTS: SUCCESS")
except Exception as e:
    _import_err = repr(e)
    _diag_info.append(f"IMPORTS: FAILED - {_import_err}")
    def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(f"Import error: {_import_err}", status_code=500)
    def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(f"Import error: {_import_err}", status_code=500)
    def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(f"Import error: {_import_err}", status_code=500)


@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@app.function_name(name="diag")
@app.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("\n".join(_diag_info), status_code=200)


@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    return handle_upload_edital(req)


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    return handle_parse_layout(req)


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    return handle_extract_params(req)
