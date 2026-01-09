# function_app.py
import sys
import logging
import traceback
from pathlib import Path

import azure.functions as func

# ---- Path bootstrap (keeps "src/" importable) ----
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ---- Optional: make log output more visible in Azure Log Stream ----
logging.basicConfig(level=logging.INFO)

# ---- Handlers (your business logic) ----
from govy.api.parse_layout import handle_parse_layout
from govy.api.extract_params import handle_extract_params
from govy.api.upload_edital import handle_upload_edital

app = func.FunctionApp()

def _safe_error_response(fn_name: str, err: Exception) -> func.HttpResponse:
    """
    Logs a full traceback to Azure Log Stream and returns a 500 with a concise message.
    This avoids "silent 500" failures where you only see Failed without stack trace.
    """
    logging.error("%s failed: %s", fn_name, str(err))
    logging.error("Traceback:\n%s", traceback.format_exc())
    return func.HttpResponse(
        f"{fn_name} failed: {type(err).__name__}: {str(err)}",
        status_code=500,
        mimetype="text/plain",
    )


@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return handle_parse_layout(req)
    except Exception as e:
        return _safe_error_response("parse_layout", e)


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return handle_extract_params(req)
    except Exception as e:
        return _safe_error_response("extract_params", e)

@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return handle_upload_edital(req)
    except Exception as e:
        return _safe_error_response("upload_edital", e)

# === GET /api/params ===
# Retorna o registry de extractors (params.json) para o frontend se auto-atualizar.

import json
import os
import azure.functions as func

@app.route(
    route="params",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION
)
def get_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        base_dir = os.path.dirname(__file__)  # pasta da raiz do projeto (onde está function_app.py)
        params_path = os.path.join(base_dir, "params.json")

        if not os.path.exists(params_path):
            return func.HttpResponse(
                json.dumps({"error": "params.json not found"}),
                status_code=500,
                mimetype="application/json",
            )

        with open(params_path, "r", encoding="utf-8") as f:
            params = json.load(f)

        # Modelo 1: só parâmetros (extractors)
        return func.HttpResponse(
            json.dumps({"extractors": params, "version": "1"}),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )

