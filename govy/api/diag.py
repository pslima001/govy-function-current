import os
import json
import azure.functions as func

def handle_diag(req: func.HttpRequest) -> func.HttpResponse:
    info = []
    
    try:
        from azure.storage.blob import BlobServiceClient
        from govy.extractors.e001_entrega import extract_e001_multi
        
        info.append("Step 1: Imports OK")
        
        conn_str = os.environ.get("AzureWebJobsStorage")
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        container = blob_service.get_container_client("editais-teste")
        
        info.append("Step 2: Container OK")
        
        json_blob = "uploads/5385e1e499981d7ca0381fb028ae3768_parsed.json"
        blob_client = container.get_blob_client(json_blob)
        raw = blob_client.download_blob().readall().decode("utf-8")
        
        info.append("Step 3: Download OK - " + str(len(raw)) + " bytes")
        
        data = json.loads(raw)
        texto = data.get("texto_completo", "")
        
        info.append("Step 4: Parse OK - texto: " + str(len(texto)) + " chars")
        
        cands = extract_e001_multi(texto, max_candidatos=3)
        
        info.append("Step 5: Extract OK - " + str(len(cands)) + " candidatos")
        
        for c in cands:
            info.append("  " + str(c.value) + " (score=" + str(c.score) + ")")
            
    except Exception as e:
        import traceback
        info.append("ERRO: " + str(e))
        info.append(traceback.format_exc())
    
    return func.HttpResponse("\n".join(info), status_code=200)