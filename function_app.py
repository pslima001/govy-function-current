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
