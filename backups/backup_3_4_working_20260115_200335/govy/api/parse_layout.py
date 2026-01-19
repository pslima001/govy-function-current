# govy/api/parse_layout.py
import azure.functions as func
import json
import os
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from datetime import datetime

def handle_parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name obrigatório"}),
                status_code=400,
                mimetype="application/json"
            )
        
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        doc_endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        doc_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service.get_blob_client(container_name, blob_name)
        pdf_bytes = blob_client.download_blob().readall()
        
        doc_client = DocumentIntelligenceClient(doc_endpoint, AzureKeyCredential(doc_key))
        poller = doc_client.begin_analyze_document("prebuilt-layout", pdf_bytes)
        result = poller.result()
        
        texto = ""
        for page in result.pages:
            for line in page.lines:
                texto += line.content + "\n"
        
        parsed_data = {
            "texto_completo": texto,
            "page_count": len(result.pages),
            "tables_count": len(result.tables) if result.tables else 0,
            "parsed_at": datetime.utcnow().isoformat() + "Z"
        }
        
        parsed_blob_name = blob_name.replace(".pdf", "_parsed.json")
        parsed_blob_client = blob_service.get_blob_client(container_name, parsed_blob_name)
        parsed_blob_client.upload_blob(json.dumps(parsed_data, ensure_ascii=False), overwrite=True)
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "source": "document_intelligence",
                "blob_name": blob_name,
                "parsed_blob": parsed_blob_name,
                "text_length": len(texto),
                "tables_count": parsed_data["tables_count"],
                "page_count": parsed_data["page_count"],
                "parsed_at": parsed_data["parsed_at"]
            }),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )