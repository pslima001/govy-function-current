# function_app.py
"""
Azure Functions - Govy Backend
Registro das funcoes HTTP
"""
import json
import azure.functions as func

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Ping
@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)

# Diag
@app.function_name(name="diag")
@app.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.diag import handle_diag
    return handle_diag(req)

# Upload Edital
@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_edital import handle_upload_edital
    return handle_upload_edital(req)

# Parse Layout
@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.parse_layout import handle_parse_layout
    return handle_parse_layout(req)

# Extract Params
@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params import handle_extract_params
    return handle_extract_params(req)

# Get Blob URL
@app.function_name(name="get_blob_url")
@app.route(route="get_blob_url", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.get_blob_url import handle_get_blob_url
    return handle_get_blob_url(req)

# Consult LLMs
@app.function_name(name="consult_llms")
@app.route(route="consult_llms", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.consult_llms import handle_consult_llms
    return handle_consult_llms(req)

# Extract Params Amplos
@app.function_name(name="extract_params_amplos")
@app.route(route="extract_params_amplos", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params_amplos(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params_amplos import handle_extract_params_amplos
    return handle_extract_params_amplos(req)

# Extract Items
@app.function_name(name="extract_items")
@app.route(route="extract_items", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_items(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_items import handle_extract_items
    return handle_extract_items(req)

# Dicionario API
@app.function_name(name="dicionario")
@app.route(route="dicionario", methods=["GET", "POST", "DELETE"], auth_level=func.AuthLevel.FUNCTION)
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

@app.function_name(name="upload_doctrine_b64")
@app.route(route="upload_doctrine_b64", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_doctrine_b64(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_doctrine_b64 import handle_upload_doctrine_b64
    return handle_upload_doctrine_b64(req)

@app.function_name(name="ingest_doctrine")
@app.route(route="ingest_doctrine", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.api.ingest_doctrine import handle_ingest_doctrine
        return handle_ingest_doctrine(req)
    except Exception as e:
        import traceback
        return func.HttpResponse(
            json.dumps(
                {"error": "ingest_doctrine failed", "details": str(e), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            status_code=500,
            mimetype="application/json",
        )

# ============================================================
# JURISPRUDENCIA ENDPOINTS
# ============================================================

@app.function_name(name="api_juris_upload")
@app.route(route="juris/upload", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_upload(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_upload import main
    return main(req)

@app.function_name(name="api_juris_fichas")
@app.route(route="juris/fichas", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_fichas(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_fichas import main
    return main(req)

@app.function_name(name="api_juris_validar")
@app.route(route="juris/validar", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_validar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_validar import main
    return main(req)

@app.function_name(name="api_juris_buscar")
@app.route(route="juris/buscar", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_buscar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_buscar import main
    return main(req)

@app.function_name(name="kb_index_upsert")
@app.route(route="kb/index/upsert", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_index_upsert(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_index_upsert import main
    return main(req)

@app.function_name(name="kb_search")
@app.route(route="kb/search", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_search(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_search import main
    return main(req)

@app.function_name(name="kb_effect_classify")
@app.route(route="kb/effect/classify", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_effect_classify(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_effect_classify import main
    return main(req)

# KB Juris Extract All
@app.function_name(name="kb_juris_extract_all")
@app.route(route="kb/juris/extract_all", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import main
    return main(req)

# KB Juris Review Queue - Listar pendentes
@app.function_name(name="kb_juris_review_list")
@app.route(route="kb/juris/review_queue", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_review_queue
    return list_review_queue(req)

# KB Juris Review Queue - Obter item
@app.function_name(name="kb_juris_review_get")
@app.route(route="kb/juris/review_queue/{item_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_get(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_review_item
    return get_review_item(req)

# KB Juris Review Queue - Aprovar item
@app.function_name(name="kb_juris_review_approve")
@app.route(route="kb/juris/review_queue/{item_id}/approve", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_approve(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import approve_review_item
    return approve_review_item(req)

# KB Juris Review Queue - Rejeitar item
@app.function_name(name="kb_juris_review_reject")
@app.route(route="kb/juris/review_queue/{item_id}/reject", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_reject(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import reject_review_item
    return reject_review_item(req)

# KB Juris - Lists & Stats
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

# ============================================================
# DIAGNOSTIC ENDPOINT (Troubleshooting)
# ============================================================

@app.function_name(name="diagnostic_full")
@app.route(route="diagnostic_full", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diagnostic_full(req: func.HttpRequest) -> func.HttpResponse:
    """Endpoint de diagnostico completo para troubleshooting"""
    import os
    
    d = {}
    
    # Python info
    d["python_version"] = sys.version
    d["sys_path"] = sys.path
    d["cwd"] = os.getcwd()
    
    # WWWROOT structure
    wwwroot = "/home/site/wwwroot"
    d["wwwroot_exists"] = os.path.exists(wwwroot)
    
    if os.path.exists(wwwroot):
        try:
            d["wwwroot_contents"] = os.listdir(wwwroot)
        except Exception as e:
            d["wwwroot_contents"] = f"ERROR: {str(e)}"
    
    # GOVY folder
    govy_path = os.path.join(wwwroot, "govy")
    d["govy_exists"] = os.path.exists(govy_path)
    
    if os.path.exists(govy_path):
        try:
            d["govy_contents"] = os.listdir(govy_path)
            
            # Subfolders
            govy_api = os.path.join(govy_path, "api")
            govy_doctrine = os.path.join(govy_path, "doctrine")
            
            d["govy_api_exists"] = os.path.exists(govy_api)
            if os.path.exists(govy_api):
                d["govy_api_files"] = os.listdir(govy_api)[:10]
            
            d["govy_doctrine_exists"] = os.path.exists(govy_doctrine)
            if os.path.exists(govy_doctrine):
                d["govy_doctrine_files"] = os.listdir(govy_doctrine)[:10]
        except Exception as e:
            d["govy_error"] = str(e)
    
    # __init__.py files
    init_files = []
    for init_path in [
        os.path.join(wwwroot, "govy", "__init__.py"),
        os.path.join(wwwroot, "govy", "api", "__init__.py"),
        os.path.join(wwwroot, "govy", "doctrine", "__init__.py"),
    ]:
        init_files.append({
            "path": init_path.replace(wwwroot, ""),
            "exists": os.path.exists(init_path)
        })
    d["init_files"] = init_files
    
    # Import tests
    import_tests = {}
    
    try:
        import govy as govy_module
        import_tests["import_govy"] = "OK"
    except Exception as e:
        import_tests["import_govy"] = f"FAILED: {str(e)}"
    
    try:
        from govy.api.ingest_doctrine import handle_ingest_doctrine
        import_tests["import_ingest_doctrine"] = "OK"
    except Exception as e:
        import_tests["import_ingest_doctrine"] = f"FAILED: {str(e)}"
    
    try:
        from govy.doctrine import pipeline
        import_tests["import_pipeline"] = "OK"
    except Exception as e:
        import_tests["import_pipeline"] = f"FAILED: {str(e)}"
    
    d["import_tests"] = import_tests
    
    # Find govy anywhere
    try:
        govy_locations = []
        for root, dirs, files in os.walk(wwwroot):
            if "govy" in dirs:
                govy_locations.append(root.replace(wwwroot, ""))
            if root.count(os.sep) - wwwroot.count(os.sep) > 2:
                break
        d["govy_found_at"] = govy_locations if govy_locations else ["NOT_FOUND"]
    except Exception as e:
        d["find_govy_error"] = str(e)
    
    return func.HttpResponse(
        body=json.dumps(d, indent=2, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )
