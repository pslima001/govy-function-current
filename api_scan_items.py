"""
API Endpoint: scan_items
Camada 1 - Scan de páginas candidatas e extração raw
Custo: ZERO (não usa Azure DI)
"""

import azure.functions as func
import json
import logging
from azure.storage.blob import BlobServiceClient
import os

# Importar módulo de extração raw
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from govy_items_raw import process_pdf_items_raw, get_candidate_pages_pdf


def get_blob_service():
    """Retorna cliente do Blob Storage"""
    conn_str = os.environ.get('AzureWebJobsStorage')
    return BlobServiceClient.from_connection_string(conn_str)


def download_pdf(blob_name: str) -> bytes:
    """Baixa PDF do blob storage"""
    blob_service = get_blob_service()
    container_name = "editais-teste"
    blob_client = blob_service.get_blob_client(container_name, blob_name)
    return blob_client.download_blob().readall()


def upload_blob(blob_name: str, data: bytes, content_type: str = "application/pdf"):
    """Faz upload de arquivo para blob storage"""
    blob_service = get_blob_service()
    container_name = "editais-teste"
    blob_client = blob_service.get_blob_client(container_name, blob_name)
    blob_client.upload_blob(data, overwrite=True, content_type=content_type)
    return blob_name


bp = func.Blueprint()


@bp.function_name("scan_items")
@bp.route(route="scan_items", methods=["POST"])
def scan_items(req: func.HttpRequest) -> func.HttpResponse:
    """
    Escaneia PDF para identificar páginas candidatas e tenta extração raw.
    
    Request:
        POST /api/scan_items
        {
            "blob_name": "uploads/abc123.pdf"
        }
        
    Response:
        {
            "scan": {
                "total_pages": 68,
                "candidates_count": 4,
                "candidate_pages": [15, 16, 17, 18],
                "candidates_detail": [...]
            },
            "extraction": {
                "total_items": 25,
                "confidence_percent": "85.0%",
                "needs_di": false,
                "recommendation": "USAR_DIRETO",
                "items": [...]
            },
            "summary": {
                "pages_scanned": 68,
                "pages_with_items": 4,
                "items_found": 25,
                "confidence": "85.0%",
                "needs_di": false
            }
        }
    """
    logging.info("scan_items: Iniciando")
    
    try:
        body = req.get_json()
        blob_name = body.get('blob_name')
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name é obrigatório"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Baixar PDF
        logging.info(f"scan_items: Baixando {blob_name}")
        pdf_bytes = download_pdf(blob_name)
        
        # Processar
        logging.info("scan_items: Processando PDF")
        result = process_pdf_items_raw(pdf_bytes)
        
        # Adicionar blob_name ao resultado
        result['blob_name'] = blob_name
        
        logging.info(f"scan_items: Concluído. {result['summary']['items_found']} itens, confiança {result['summary']['confidence']}")
        
        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"scan_items: Erro - {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@bp.function_name("extract_candidate_pages")
@bp.route(route="extract_candidate_pages", methods=["POST"])
def extract_candidate_pages(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extrai apenas as páginas candidatas como novo PDF.
    
    Request:
        POST /api/extract_candidate_pages
        {
            "blob_name": "uploads/abc123.pdf",
            "pages": [15, 16, 17, 18]  // Opcional - se não informado, escaneia automaticamente
        }
        
    Response:
        {
            "original_blob": "uploads/abc123.pdf",
            "extracted_blob": "uploads/abc123_pages_15-18.pdf",
            "pages_extracted": [15, 16, 17, 18],
            "message": "PDF com 4 páginas extraído com sucesso"
        }
    """
    logging.info("extract_candidate_pages: Iniciando")
    
    try:
        body = req.get_json()
        blob_name = body.get('blob_name')
        pages = body.get('pages')  # Opcional
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name é obrigatório"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Baixar PDF original
        logging.info(f"extract_candidate_pages: Baixando {blob_name}")
        pdf_bytes = download_pdf(blob_name)
        
        # Extrair páginas
        logging.info(f"extract_candidate_pages: Extraindo páginas {pages or 'auto'}")
        extracted_pdf = get_candidate_pages_pdf(pdf_bytes, pages)
        
        # Se pages não foi informado, descobrir quais foram extraídas
        if pages is None:
            from govy_items_raw import scan_pdf_for_item_pages
            scan_result = scan_pdf_for_item_pages(pdf_bytes)
            pages = scan_result['candidate_pages']
        
        # Gerar nome do novo blob
        base_name = blob_name.replace('.pdf', '')
        pages_str = f"{pages[0]}-{pages[-1]}" if pages else "none"
        new_blob_name = f"{base_name}_pages_{pages_str}.pdf"
        
        # Upload do PDF extraído
        logging.info(f"extract_candidate_pages: Salvando {new_blob_name}")
        upload_blob(new_blob_name, extracted_pdf)
        
        return func.HttpResponse(
            json.dumps({
                "original_blob": blob_name,
                "extracted_blob": new_blob_name,
                "pages_extracted": pages,
                "pages_count": len(pages),
                "message": f"PDF com {len(pages)} páginas extraído com sucesso"
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"extract_candidate_pages: Erro - {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
