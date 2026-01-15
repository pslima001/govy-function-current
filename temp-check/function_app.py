import sys
import os
import logging
import azure.functions as func

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = func.FunctionApp()

@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)

@app.function_name(name="diag")
@app.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    info = []
    info.append(f"ROOT: {ROOT}")
    info.append(f"sys.path: {sys.path[:3]}")
    info.append(f"govy exists: {os.path.exists(os.path.join(ROOT, 'govy'))}")
    return func.HttpResponse("\n".join(info), status_code=200)

@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.api.upload_edital import handle_upload_edital
        return handle_upload_edital(req)
    except Exception as e:
        return func.HttpResponse(f"Import error: {repr(e)}", status_code=500)

@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.api.parse_layout import handle_parse_layout
        return handle_parse_layout(req)
    except Exception as e:
        return func.HttpResponse(f"Import error: {repr(e)}", status_code=500)

@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.api.extract_params import handle_extract_params
        return handle_extract_params(req)
    except Exception as e:
        return func.HttpResponse(f"Import error: {repr(e)}", status_code=500)
