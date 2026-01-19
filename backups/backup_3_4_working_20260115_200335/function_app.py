# function_app.py
"""
Azure Functions - Govy Backend

Este arquivo define as Azure Functions para processamento de editais.
FUNCIONAL: Versão estável com 4/4 parâmetros funcionando.

Última atualização: 15/01/2026
Tag de referência: v1.0-stable
"""
import sys
import os
import logging
import json

import azure.functions as func

# Adiciona o diretório raiz ao path para imports
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Inicializa o app
app = func.FunctionApp()

# =============================================================================
# DIAGNÓSTICO DE STARTUP
# =============================================================================
_diag_info = []
_diag_info.append(f"ROOT: {ROOT}")
_diag_info.append(f"sys.path[0:3]: {sys.path[:3]}")

# Verifica estrutura de diretórios
govy_path = os.path.join(ROOT, "govy")
_diag_info.append(f"govy exists: {os.path.exists(govy_path)}")

extractors_path = os.path.join(ROOT, "govy", "extractors")
_diag_info.append(f"govy/extractors exists: {os.path.exists(extractors_path)}")

if os.path.exists(extractors_path):
    _diag_info.append(f"extractors contents: {os.listdir(extractors_path)}")

# =============================================================================
# IMPORTS DOS HANDLERS
# =============================================================================
_import_error = None

try:
    from govy.api.upload_edital import handle_upload_edital
    from govy.api.parse_layout import handle_parse_layout
    from govy.api.extract_params import handle_extract_params
    _diag_info.append("IMPORTS govy.api: SUCCESS")
except Exception as e:
    _import_error = repr(e)
    _diag_info.append(f"IMPORTS govy.api: FAILED - {_import_error}")
    
    # Handlers de fallback em caso de erro de import
    def handle_upload_edital(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(
            json.dumps({"error": f"Import error: {_import_error}"}),
            status_code=500,
            mimetype="application/json"
        )
    
    def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(
            json.dumps({"error": f"Import error: {_import_error}"}),
            status_code=500,
            mimetype="application/json"
        )
    
    def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(
            json.dumps({"error": f"Import error: {_import_error}"}),
            status_code=500,
            mimetype="application/json"
        )

# =============================================================================
# FUNÇÕES AZURE
# =============================================================================

@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    """Healthcheck - retorna 'pong' se o serviço está funcionando."""
    return func.HttpResponse("pong", status_code=200)


@app.function_name(name="diag")
@app.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    """Diagnóstico - retorna informações sobre o ambiente."""
    return func.HttpResponse(
        "\n".join(_diag_info),
        status_code=200,
        mimetype="text/plain"
    )


@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    """Upload de edital PDF para processamento."""
    return handle_upload_edital(req)


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    """Parse do layout do documento via Azure Document Intelligence."""
    return handle_parse_layout(req)


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """Extração de parâmetros do edital."""
    return handle_extract_params(req)
