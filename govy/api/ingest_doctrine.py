import json
import os
import traceback
import azure.functions as func
from govy.utils.azure_clients import get_blob_service_client

from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once


def handle_ingest_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    """
    Ingestão de doutrina (processa uma vez):
      - lê DOCX do container DOCTRINE_CONTAINER_NAME
      - salva JSON processado no DOCTRINE_PROCESSED_CONTAINER_NAME

    Retorna erro detalhado em JSON para diagnóstico.
    """
    try:
        try:
            data = req.get_json()
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": "Envie JSON válido.", "details": str(e)}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        required = [
            "blob_name",
            "etapa_processo",
            "tema_principal",
            
        ]
        missing = [k for k in required if k not in data]
        if missing:
            return func.HttpResponse(
                json.dumps({"error": "Campos obrigatórios ausentes.", "missing": missing}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        ingest_req = DoctrineIngestRequest(
            blob_name=str(data["blob_name"]),
            etapa_processo=str(data["etapa_processo"]),
            tema_principal=str(data["tema_principal"]),
            autor=data.get("autor", ""),
            obra=data.get("obra", ""),
            edicao=data.get("edicao", ""),
            ano=int(data.get("ano", 0) or 0),
            capitulo=data.get("capitulo", ""),
            secao=data.get("secao", ""),
            force_reprocess=bool(data.get("force_reprocess", False)),
        )

        container_source = os.getenv("DOCTRINE_CONTAINER_NAME", "kb-doutrina-raw")
        container_processed = os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "kb-doutrina-processed")

        blob_service = get_blob_service_client()

        result = ingest_doctrine_process_once(
            blob_service=blob_service,
            container_source=container_source,
            container_processed=container_processed,
            req=ingest_req,
        )

        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps(
                {"error": "Unhandled exception in ingest_doctrine", "details": str(e), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            status_code=500,
            mimetype="application/json",
        )
