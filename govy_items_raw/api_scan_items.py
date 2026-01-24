import azure.functions as func
import json
import logging
import os

def get_blob_service():
    from azure.storage.blob import BlobServiceClient
    conn_str = os.environ.get('AzureWebJobsStorage') or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    return BlobServiceClient.from_connection_string(conn_str)

def download_pdf(blob_name: str) -> bytes:
    blob_service = get_blob_service()
    blob_client = blob_service.get_blob_client("editais-teste", blob_name)
    return blob_client.download_blob().readall()

def upload_blob(blob_name: str, data: bytes, content_type: str = "application/pdf"):
    blob_service = get_blob_service()
    blob_client = blob_service.get_blob_client("editais-teste", blob_name)
    blob_client.upload_blob(data, overwrite=True, content_type=content_type)
    return blob_name

def handle_scan_items(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("scan_items: Iniciando")
    try:
        body = req.get_json()
        blob_name = body.get('blob_name')
        if not blob_name:
            return func.HttpResponse(json.dumps({"error": "blob_name obrigatorio"}), status_code=400, mimetype="application/json")
        logging.info(f"scan_items: Baixando {blob_name}")
        pdf_bytes = download_pdf(blob_name)
        logging.info("scan_items: Processando PDF")
        from govy_items_raw.main import process_pdf_items_raw
        result = process_pdf_items_raw(pdf_bytes)
        result['blob_name'] = blob_name
        result['version'] = 'v12-fix226'
        logging.info(f"scan_items: Concluido. {result['summary']['items_found']} itens")
        return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200, mimetype="application/json")
    except Exception as e:
        logging.error(f"scan_items: Erro - {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")

def handle_extract_candidate_pages(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("extract_candidate_pages: Iniciando")
    try:
        body = req.get_json()
        blob_name = body.get('blob_name')
        pages = body.get('pages')
        if not blob_name:
            return func.HttpResponse(json.dumps({"error": "blob_name obrigatorio"}), status_code=400, mimetype="application/json")
        logging.info(f"extract_candidate_pages: Baixando {blob_name}")
        pdf_bytes = download_pdf(blob_name)
        logging.info(f"extract_candidate_pages: Extraindo paginas {pages or 'auto'}")
        from govy_items_raw.main import get_candidate_pages_pdf
        extracted_pdf = get_candidate_pages_pdf(pdf_bytes, pages)
        if pages is None:
            from govy_items_raw.pdf_scanner import scan_pdf_for_item_pages
            scan_result = scan_pdf_for_item_pages(pdf_bytes)
            pages = scan_result['candidate_pages']
        base_name = blob_name.replace('.pdf', '')
        pages_str = f"{pages[0]}-{pages[-1]}" if pages else "none"
        new_blob_name = f"{base_name}_pages_{pages_str}.pdf"
        logging.info(f"extract_candidate_pages: Salvando {new_blob_name}")
        upload_blob(new_blob_name, extracted_pdf)
        return func.HttpResponse(json.dumps({"original_blob": blob_name, "extracted_blob": new_blob_name,
                                              "pages_extracted": pages, "pages_count": len(pages),
                                              "message": f"PDF com {len(pages)} paginas extraido"}, ensure_ascii=False),
                                  status_code=200, mimetype="application/json")
    except Exception as e:
        logging.error(f"extract_candidate_pages: Erro - {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")

