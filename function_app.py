# function_app.py
"""
Azure Functions - Govy Backend
Registro das funcoes HTTP
"""
import json
import typing
import logging
import sys
from pathlib import Path

import azure.functions as func

# CORS helpers (KB Content Hub)
from govy.api.cors import cors_preflight, cors_headers


# ---- Path bootstrap (mantÃ©m o padrÃ£o do seu projeto) ----
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


# ============================================================
# CORE
# ============================================================

@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@app.function_name(name="diag")
@app.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.diag import handle_diag
    return handle_diag(req)


@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_edital import handle_upload_edital
    return handle_upload_edital(req)


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.parse_layout import handle_parse_layout
    return handle_parse_layout(req)


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params import handle_extract_params
    return handle_extract_params(req)


@app.function_name(name="get_blob_url")
@app.route(route="get_blob_url", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.get_blob_url import handle_get_blob_url
    return handle_get_blob_url(req)


@app.function_name(name="consult_llms")
@app.route(route="consult_llms", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.consult_llms import handle_consult_llms
    return handle_consult_llms(req)


@app.function_name(name="extract_params_amplos")
@app.route(route="extract_params_amplos", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params_amplos(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params_amplos import handle_extract_params_amplos
    return handle_extract_params_amplos(req)


@app.function_name(name="extract_items")
@app.route(route="extract_items", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_items(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_items import handle_extract_items
    return handle_extract_items(req)


@app.function_name(name="dicionario")
@app.route(route="dicionario", methods=["GET", "POST", "DELETE"], auth_level=func.AuthLevel.FUNCTION)
def dicionario(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.dicionario_api import handle_dicionario
    return handle_dicionario(req)


# ============================================================
# DOUTRINA ENDPOINTS
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
# JURISPRUDENCIA ENDPOINTS (antigos)
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


# ============================================================
# KB SEARCH / UPSERT (mantÃ©m como estÃ¡, jÃ¡ tinha OPTIONS)
# ============================================================

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


# ============================================================
# KB JURIS PIPELINE (review queue etc.)
# ============================================================

@app.function_name(name="kb_juris_extract_all")
@app.route(route="kb/juris/extract_all", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import main
    return main(req)


@app.function_name(name="kb_juris_review_list")
@app.route(route="kb/juris/review_queue", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_review_queue
    return list_review_queue(req)


@app.function_name(name="kb_juris_review_get")
@app.route(route="kb/juris/review_queue/{item_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_get(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_review_item
    return get_review_item(req)


@app.function_name(name="kb_juris_review_approve")
@app.route(route="kb/juris/review_queue/{item_id}/approve", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_approve(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import approve_review_item
    return approve_review_item(req)


@app.function_name(name="kb_juris_review_reject")
@app.route(route="kb/juris/review_queue/{item_id}/reject", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_reject(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import reject_review_item
    return reject_review_item(req)


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
# KB CONTENT HUB ENDPOINTS (Paste/CRUD) + CORS/OPTIONS
# ============================================================

# KB Juris Paste (UI costuma chamar via browser) - garantir OPTIONS + CORS
@app.function_name(name="kb_juris_paste")
@app.route(route="kb/juris/paste", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_paste(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_juris_paste import handle_kb_juris_paste
    resp = handle_kb_juris_paste(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_list")
@app.route(route="kb/content/list", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_list(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_list
    resp = handle_kb_content_list(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_paste")
@app.route(route="kb/content/paste", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_paste(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_paste
    resp = handle_kb_content_paste(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_approve")
@app.route(route="kb/content/{id}/approve", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_approve(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_approve
    resp = handle_kb_content_approve(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_reject")
@app.route(route="kb/content/{id}/reject", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_reject(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_reject
    resp = handle_kb_content_reject(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_update")
@app.route(route="kb/content/{id}/update", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_update(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_update
    resp = handle_kb_content_update(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_delete")
@app.route(route="kb/content/{id}/delete", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_delete(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_delete
    resp = handle_kb_content_delete(req)
    resp.headers.update(cors_headers(req))
    return resp


@app.function_name(name="kb_content_restore")
@app.route(route="kb/content/{id}/restore", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_restore(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_restore
    resp = handle_kb_content_restore(req)
    resp.headers.update(cors_headers(req))
    return resp


# ============================================================
# DIAGNOSTIC ENDPOINT (Troubleshooting)
# ============================================================

@app.function_name(name="diagnostic_full")
@app.route(route="diagnostic_full", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diagnostic_full(req: func.HttpRequest) -> func.HttpResponse:
    """Endpoint de diagnostico completo para troubleshooting"""
    import os

    d: Dict[str, Any] = {}

    d["python_version"] = sys.version
    d["sys_path"] = sys.path
    d["cwd"] = os.getcwd()

    wwwroot = "/home/site/wwwroot"
    d["wwwroot_exists"] = os.path.exists(wwwroot)
    if os.path.exists(wwwroot):
        try:
            d["wwwroot_contents"] = os.listdir(wwwroot)
        except Exception as e:
            d["wwwroot_contents"] = f"ERROR: {str(e)}"

    govy_path = os.path.join(wwwroot, "govy")
    d["govy_exists"] = os.path.exists(govy_path)

    if os.path.exists(govy_path):
        try:
            d["govy_contents"] = os.listdir(govy_path)

            govy_api = os.path.join(govy_path, "api")
            govy_doctrine = os.path.join(govy_path, "doctrine")

            d["govy_api_exists"] = os.path.exists(govy_api)
            if os.path.exists(govy_api):
                d["govy_api_files"] = os.listdir(govy_api)[:50]

            d["govy_doctrine_exists"] = os.path.exists(govy_doctrine)
            if os.path.exists(govy_doctrine):
                d["govy_doctrine_files"] = os.listdir(govy_doctrine)[:50]
        except Exception as e:
            d["govy_error"] = str(e)

    init_files = []
    for init_path in [
        os.path.join(wwwroot, "govy", "__init__.py"),
        os.path.join(wwwroot, "govy", "api", "__init__.py"),
        os.path.join(wwwroot, "govy", "doctrine", "__init__.py"),
    ]:
        init_files.append({"path": init_path.replace(wwwroot, ""), "exists": os.path.exists(init_path)})
    d["init_files"] = init_files

    import_tests = {}
    try:
        import govy as govy_module  # noqa: F401
        import_tests["import_govy"] = "OK"
    except Exception as e:
        import_tests["import_govy"] = f"FAILED: {str(e)}"

    try:
        from govy.api.ingest_doctrine import handle_ingest_doctrine  # noqa: F401
        import_tests["import_ingest_doctrine"] = "OK"
    except Exception as e:
        import_tests["import_ingest_doctrine"] = f"FAILED: {str(e)}"

    try:
        from govy.doctrine import pipeline  # noqa: F401
        import_tests["import_pipeline"] = "OK"
    except Exception as e:
        import_tests["import_pipeline"] = f"FAILED: {str(e)}"

    d["import_tests"] = import_tests

    return func.HttpResponse(
        body=json.dumps(d, indent=2, ensure_ascii=False),
        mimetype="application/json",
        status_code=200,
    )



# ============================================================
# QUEUE TRIGGER: parse-tce-queue
# ============================================================
@app.function_name(name="parse_tce_pdf")
@app.queue_trigger(arg_name="msg", queue_name="parse-tce-queue", connection="AzureWebJobsStorage")
def parse_tce_pdf(msg: func.QueueMessage) -> None:
    msg_text = msg.get_body().decode("utf-8")
    logging.info(f"[parse-tce-queue] Recebida msg: {msg_text[:200]}")
    from govy.api.tce_queue_handler import handle_parse_tce_pdf
    result = handle_parse_tce_pdf(msg_text)
    status = result.get("status", "unknown")
    if status == "success":
        logging.info(f"[parse-tce-queue] OK: {result.get('blob_path')}")
    elif status == "skipped":
        logging.warning(f"[parse-tce-queue] Pulado: {result.get('blob_path')} - {result.get('reason')}")
    else:
        logging.error(f"[parse-tce-queue] ERRO: {result.get('blob_path')} - {result.get('error')}")
        raise RuntimeError(f"parse_tce_pdf failed: {result.get('error')}")


# ============================================================
# ENDPOINT: POST /api/kb/juris/enqueue-tce (via SDK)
# ============================================================
@app.function_name(name="enqueue_tce")
@app.route(route="kb/juris/enqueue-tce", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def enqueue_tce(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}
    from govy.api.tce_queue_handler import handle_enqueue_tce
    result = handle_enqueue_tce(body)
    msgs = result.get("messages", [])
    if msgs:
        import os
        from azure.storage.queue import QueueClient
        qc = QueueClient.from_connection_string(os.environ["AzureWebJobsStorage"], "parse-tce-queue")  # ALLOW_CONNECTION_STRING_OK
        try:
            qc.create_queue()
        except Exception:
            pass
        for m in msgs:
            qc.send_message(json.dumps(m, ensure_ascii=False))
        logging.info(f"[enqueue-tce] {len(msgs)} msgs enfileiradas via SDK")
    # result.pop("messages", None)  # mantido para scripts
    return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200, mimetype="application/json")


# ============================================================
# TESTE: verificar imports e conexao TCE
# ============================================================
@app.function_name(name="test_tce")
@app.route(route="test/tce", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def test_tce(req: func.HttpRequest) -> func.HttpResponse:
    import os
    d = {}
    d["TCE_STORAGE_CONNECTION"] = "SET" if os.environ.get("TCE_STORAGE_CONNECTION") else "MISSING"
    d["AzureWebJobsStorage"] = "SET" if os.environ.get("AzureWebJobsStorage") else "MISSING"
    try:
        from govy.api.tce_parser_v3 import parse_pdf_bytes
        d["import_parser"] = "OK"
    except Exception as e:
        d["import_parser"] = str(e)
    try:
        from govy.api.mapping_tce_to_kblegal import transform_parser_to_kblegal
        d["import_mapping"] = "OK"
    except Exception as e:
        d["import_mapping"] = str(e)
    try:
        from govy.api.tce_queue_handler import handle_enqueue_tce, handle_parse_tce_pdf
        d["import_handler"] = "OK"
    except Exception as e:
        d["import_handler"] = str(e)
    try:
        from azure.storage.blob import BlobServiceClient
        cs = os.environ.get("TCE_STORAGE_CONNECTION", "")
        svc = BlobServiceClient.from_connection_string(cs)  # ALLOW_CONNECTION_STRING_OK
        cc = svc.get_container_client("tce-jurisprudencia")
        blobs = list(cc.list_blobs(name_starts_with="tce-sp/acordaos/", results_per_page=2))
        d["tce_blobs"] = len(blobs)
    except Exception as e:
        d["tce_blobs_error"] = str(e)
    return func.HttpResponse(json.dumps(d, indent=2), mimetype="application/json")

# TESTE: processar 1 PDF direto (sem fila)
@app.function_name(name="test_parse_one")
@app.route(route="test/parse-one", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def test_parse_one(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        from govy.api.tce_queue_handler import handle_parse_tce_pdf
        result = handle_parse_tce_pdf(body)
        return func.HttpResponse(json.dumps(result, ensure_ascii=False, indent=2), mimetype="application/json")
    except Exception as e:
        import traceback
        return func.HttpResponse(json.dumps({"error": str(e), "traceback": traceback.format_exc()}, indent=2), status_code=500, mimetype="application/json")

# TESTE: ver output do parser raw
@app.function_name(name="test_parser_raw")
@app.route(route="test/parser-raw", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def test_parser_raw(req: func.HttpRequest) -> func.HttpResponse:
    try:
        import os
        body = req.get_json()
        blob_path = body["blob_path"]
        from azure.storage.blob import BlobServiceClient
        svc = BlobServiceClient.from_connection_string(os.environ["TCE_STORAGE_CONNECTION"])  # ALLOW_CONNECTION_STRING_OK
        pdf = svc.get_container_client("tce-jurisprudencia").get_blob_client(blob_path).download_blob().readall()
        from govy.api.tce_parser_v3 import parse_pdf_bytes
        result = parse_pdf_bytes(pdf, include_text=False)
        summary = {k: (v[:2000] if isinstance(v, str) and len(v)>2000 else v) for k,v in result.items()}
        return func.HttpResponse(json.dumps(summary, ensure_ascii=False, indent=2, default=str), mimetype="application/json")
    except Exception as e:
        import traceback
        return func.HttpResponse(json.dumps({"error": str(e), "tb": traceback.format_exc()}, indent=2), status_code=500, mimetype="application/json")

# TESTE: Document Intelligence + parser regex
@app.function_name(name="test_di_parser")
@app.route(route="test/di-parser", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def test_di_parser(req: func.HttpRequest) -> func.HttpResponse:
    try:
        import os
        body = req.get_json()
        blob_path = body["blob_path"]
        from azure.storage.blob import BlobServiceClient
        svc = BlobServiceClient.from_connection_string(os.environ["TCE_STORAGE_CONNECTION"])  # ALLOW_CONNECTION_STRING_OK
        pdf = svc.get_container_client("tce-jurisprudencia").get_blob_client(blob_path).download_blob().readall()
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        di = DocumentIntelligenceClient(os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"], AzureKeyCredential(os.environ["DOCUMENT_INTELLIGENCE_KEY"]))
        poller = di.begin_analyze_document("prebuilt-read", body=pdf, content_type="application/pdf")
        di_result = poller.result()
        di_text = di_result.content
        from govy.api.tce_parser_v3 import parse_text
        parsed = parse_text(di_text, include_text=False)
        summary = {k: (v[:150] if isinstance(v, str) and len(v)>150 else v) for k,v in parsed.items()}
        summary["_di_text_len"] = len(di_text)
        summary["_di_text_sample"] = di_text[:500]
        return func.HttpResponse(json.dumps(summary, ensure_ascii=False, indent=2, default=str), mimetype="application/json")
    except Exception as e:
        import traceback
        return func.HttpResponse(json.dumps({"error": str(e), "tb": traceback.format_exc()}, indent=2), status_code=500, mimetype="application/json")


# ============================================================
# TESTE: OpenAI extrai candidatos de campos do acordao
# ============================================================
@app.function_name(name="test_ai_extract")
@app.route(route="test/ai-extract", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def test_ai_extract(req: func.HttpRequest) -> func.HttpResponse:
    try:
        import os, fitz
        from openai import OpenAI
        body = req.get_json()
        blob_path = body["blob_path"]
        from azure.storage.blob import BlobServiceClient
        svc = BlobServiceClient.from_connection_string(os.environ["TCE_STORAGE_CONNECTION"])  # ALLOW_CONNECTION_STRING_OK
        pdf_bytes = svc.get_container_client("tce-jurisprudencia").get_blob_client(blob_path).download_blob().readall()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = chr(10).join(page.get_text() for page in doc)
        if len(text.strip()) < 50:
            return func.HttpResponse(json.dumps({"blob_path": blob_path, "error": "texto_curto", "chars": len(text)}, ensure_ascii=False), mimetype="application/json")
        text_t = text[:12000]
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        prompt = (
            "Analise este acordao do TCE-SP. Extraia SOMENTE os textos abaixo, sem comentarios, sem explicacoes.\n"
            "Se nao encontrar, responda __MISSING__.\n\n"
            "1. DISPOSITIVO: trecho exato da decisao final (apos ANTE O EXPOSTO, DIANTE DO EXPOSTO, ACORDAM, DECIDIU-SE, VOTO:, pelo meu voto). Copie o trecho inteiro.\n"
            "2. EMENTA: se houver secao EMENTA: ou resumo no inicio. Se nao, __MISSING__.\n"
            "3. HOLDING: classifique: DETERMINOU_AJUSTE | AFASTOU | ORIENTOU | SANCIONOU | ABSOLVEU | ARQUIVOU | __MISSING__\n"
            "4. EFFECT: classifique: RIGORIZA | FLEXIBILIZA | CONDICIONAL | __MISSING__\n"
            "5. KEY_CITATION: trecho mais importante para citar numa defesa juridica (max 300 chars).\n\n"
            'Responda EXATAMENTE neste formato JSON, sem markdown:\n'
            '{"dispositivo": "...", "ementa": "...", "holding": "...", "effect": "...", "key_citation": "..."}\n\n'
            "TEXTO:\n" + text_t
        )
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0, max_tokens=2000)
        ai_text = response.choices[0].message.content.strip()
        try:
            clean = ai_text
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            ai_fields = json.loads(clean)
        except Exception:
            ai_fields = {"raw_response": ai_text, "parse_error": True}
        ai_fields["blob_path"] = blob_path
        ai_fields["chars"] = len(text)
        ai_fields["pages"] = len(doc)
        ai_fields["tokens_used"] = response.usage.total_tokens if response.usage else 0
        return func.HttpResponse(json.dumps(ai_fields, ensure_ascii=False, indent=2), mimetype="application/json")
    except Exception as e:
        import traceback
        return func.HttpResponse(json.dumps({"error": str(e), "tb": traceback.format_exc()}, indent=2), status_code=500, mimetype="application/json")


