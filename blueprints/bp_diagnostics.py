import json

import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="test_tce")
@bp.route(route="test/tce", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
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


@bp.function_name(name="test_parse_one")
@bp.route(route="test/parse-one", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def test_parse_one(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        from govy.api.tce_queue_handler import handle_parse_tce_pdf
        result = handle_parse_tce_pdf(body)
        return func.HttpResponse(json.dumps(result, ensure_ascii=False, indent=2), mimetype="application/json")
    except Exception as e:
        import traceback
        return func.HttpResponse(json.dumps({"error": str(e), "traceback": traceback.format_exc()}, indent=2), status_code=500, mimetype="application/json")


@bp.function_name(name="test_parser_raw")
@bp.route(route="test/parser-raw", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
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


@bp.function_name(name="test_di_parser")
@bp.route(route="test/di-parser", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
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


@bp.function_name(name="test_ai_extract")
@bp.route(route="test/ai-extract", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
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
