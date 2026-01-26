# govy/api/extract_params_amplos.py
import json
import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import os

logger = logging.getLogger(__name__)

def _get_blob_client():
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")
    return BlobServiceClient.from_connection_string(conn_str)

def _load_parsed_json(blob_name: str) -> dict:
    blob_service = _get_blob_client()
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
    
    if blob_name.endswith('_parsed.json'):
        json_name = blob_name
    else:
        json_name = blob_name.replace('.pdf', '_parsed.json')
    
    blob_client = blob_service.get_blob_client(container=container_name, blob=json_name)
    data = blob_client.download_blob().readall()
    return json.loads(data.decode('utf-8'))

def handle_extract_params_amplos(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.extractors.parametros_amplos import extract_all, fix_encoding
        
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON"}),
                status_code=400,
                mimetype="application/json"
            )
        
        blob_name = body.get("blob_name")
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        parsed_data = _load_parsed_json(blob_name)
        texto = parsed_data.get("texto_completo", "")
        
        if not texto:
            paginas = parsed_data.get("paginas", [])
            texto = "\n".join(p.get("texto", "") for p in paginas)
        
        texto = fix_encoding(texto)
        resultados = extract_all(texto)
        
        total = len(resultados)
        encontrados = sum(1 for r in resultados.values() if r.get("encontrado"))
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "parametros": resultados,
                "resumo": {
                    "total": total,
                    "encontrados": encontrados,
                    "taxa_sucesso": f"{100*encontrados//total}%"
                }
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logger.exception(f"Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
