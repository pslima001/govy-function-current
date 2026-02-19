"""
govy/api/kb_juris_paste.py

Endpoint para colar texto de jurisprudência.
POST /api/kb/juris/paste

Versão: 1.0
Data: 05/02/2026
"""

import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import azure.functions as func
from azure.storage.blob import BlobServiceClient
from govy.utils.azure_clients import get_blob_service_client as _get_blob_svc

# Lazy imports para evitar cold start issues
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

KB_RAW_CONTAINER = os.environ.get("KB_RAW_CONTAINER", "kb-raw")
KB_PROCESSED_CONTAINER = os.environ.get("KB_PROCESSED_CONTAINER", "kb-processed")


def get_blob_service_client():
    """Obtém cliente do Blob Storage."""
    return _get_blob_svc()


def ensure_containers_exist(blob_service: BlobServiceClient):
    """Cria containers se não existirem."""
    for container_name in [KB_RAW_CONTAINER, KB_PROCESSED_CONTAINER, "kb-trash"]:
        try:
            container_client = blob_service.get_container_client(container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Container {container_name} criado")
        except Exception as e:
            logger.warning(f"Erro ao verificar/criar container {container_name}: {e}")


def compute_sha256(text: str) -> str:
    """Calcula SHA256 do texto."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def check_sha_exists(blob_service: BlobServiceClient, sha: str) -> bool:
    """Verifica se SHA já existe (raw ou processed)."""
    # Verificar no raw
    raw_container = blob_service.get_container_client(KB_RAW_CONTAINER)
    raw_blob_name = f"jurisprudencia/paste/{sha}.txt"
    raw_blob = raw_container.get_blob_client(raw_blob_name)
    if raw_blob.exists():
        return True
    
    # Verificar no processed (prefixo variável)
    processed_container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
    # Listar blobs com o sha no nome
    prefix = "jurisprudencia/"
    for blob in processed_container.list_blobs(name_starts_with=prefix):
        if sha in blob.name:
            return True
    
    return False


def save_raw_text(blob_service: BlobServiceClient, text: str, sha: str) -> str:
    """Salva texto raw no blob storage."""
    container = blob_service.get_container_client(KB_RAW_CONTAINER)
    blob_name = f"jurisprudencia/paste/{sha}.txt"
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(text.encode('utf-8'), overwrite=True)
    return blob_name


def build_processed_blob_name(metadata: Dict, sha: str) -> str:
    """Constrói path do blob processado."""
    family = metadata.get('tribunal_family') or 'UNKNOWN'
    tribunal = metadata.get('tribunal') or 'UNKNOWN'
    year = metadata.get('year') or 0
    
    return f"jurisprudencia/{family}/{tribunal}/{year}/{sha}.json"


def create_processed_payload(
    text: str,
    sha: str,
    raw_blob_name: str,
    metadata: Dict,
    review_status: str,
    created_by: str,
    source_label: Optional[str] = None
) -> Dict[str, Any]:
    """Cria payload do documento processado (processed_juris_v1)."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Criar chunk simples (1 chunk com texto completo)
    chunk_id = f"juris--{sha}--0"
    
    # Mapear tribunal para campos do kb-legal
    tribunal = metadata.get('tribunal')
    uf = metadata.get('uf')
    year = metadata.get('year') or 0
    
    # Chunk para indexação
    chunk = {
        "chunk_id": chunk_id,
        "doc_type": "jurisprudencia",
        "content": text[:10000],  # Limitar tamanho para indexação
        "citation": metadata.get('citation', ''),
        "year": year,
        "authority_score": 0.85,
        "tribunal": tribunal,
        "uf": uf,
        "secao": "tese",
        "procedural_stage": None,
        "holding_outcome": None,
        "remedy_type": None,
        "effect": None,
        "is_current": True
    }
    
    payload = {
        "kind": "processed_juris_v1",
        "status": "processed",
        "review_status": review_status,
        "generated_at": now,
        
        "source": {
            "input_type": "paste",
            "raw_container": KB_RAW_CONTAINER,
            "raw_blob_name": raw_blob_name,
            "source_sha": sha,
            "source_label": source_label
        },
        
        "detected": {
            "tribunal_family": metadata.get('tribunal_family'),
            "tribunal": tribunal,
            "uf": uf,
            "case_number_primary": metadata.get('case_number_primary'),
            "case_numbers_secondary": metadata.get('case_numbers_secondary', []),
            "year": year,
            "confidence": metadata.get('confidence', 0),
            "signals": metadata.get('signals', [])
        },
        
        "content": {
            "content_raw": text,
            "language": "pt-BR",
            "char_count": len(text)
        },
        
        "chunks": [chunk],
        
        "dedup": {
            "sha_duplicate": False,
            "semantic_duplicate": False,
            "near_matches": []
        },
        
        "admin": {
            "created_by": created_by,
            "created_at": now,
            "notes": "",
            "deleted_at": None,
            "deleted_by": None,
            "hard_deleted": False
        }
    }
    
    return payload


def save_processed(blob_service: BlobServiceClient, payload: Dict, blob_name: str) -> None:
    """Salva documento processado no blob."""
    container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(
        json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'),
        overwrite=True
    )


def index_chunks_to_kb(chunks: list, search_endpoint: str, search_key: str, index_name: str) -> Dict:
    """Indexa chunks no Azure Search."""
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        
        client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(search_key)
        )
        
        # Preparar documentos para indexação
        docs = []
        for chunk in chunks:
            doc = {
                "chunk_id": chunk["chunk_id"],
                "doc_type": chunk["doc_type"],
                "content": chunk["content"],
                "citation": chunk.get("citation", ""),
                "year": chunk.get("year", 0),
                "authority_score": chunk.get("authority_score", 0.5),
                "tribunal": chunk.get("tribunal"),
                "uf": chunk.get("uf"),
                "secao": chunk.get("secao"),
                "procedural_stage": chunk.get("procedural_stage"),
                "holding_outcome": chunk.get("holding_outcome"),
                "remedy_type": chunk.get("remedy_type"),
                "effect": chunk.get("effect"),
                "is_current": chunk.get("is_current", True),
                "source": "kb-paste"
            }
            docs.append(doc)
        
        # Indexar
        result = client.upload_documents(documents=docs)
        
        indexed = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        
        return {"indexed": indexed, "failed": failed}
        
    except Exception as e:
        logger.error(f"Erro ao indexar chunks: {e}")
        return {"indexed": 0, "failed": len(chunks), "error": str(e)}


# =============================================================================
# HANDLER HTTP
# =============================================================================

def handle_kb_juris_paste(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handler para POST /api/kb/juris/paste
    
    Request body:
    {
        "text": "texto integral colado",
        "source_label": "opcional",
        "force_reprocess": false,
        "created_by": "paulo"
    }
    """
    try:
        # Parse request
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "JSON inválido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        text = body.get("text", "").strip()
        if not text:
            return func.HttpResponse(
                json.dumps({"error": "Campo 'text' é obrigatório"}),
                status_code=400,
                mimetype="application/json"
            )
        
        source_label = body.get("source_label")
        force_reprocess = body.get("force_reprocess", False)
        created_by = body.get("created_by", "anonymous")
        
        # Calcular SHA
        sha = compute_sha256(text)
        
        # Conectar ao blob
        blob_service = get_blob_service_client()
        ensure_containers_exist(blob_service)
        
        # Verificar duplicata
        if not force_reprocess and check_sha_exists(blob_service, sha):
            return func.HttpResponse(
                json.dumps({
                    "status": "duplicate",
                    "source_sha": sha,
                    "message": "Documento já existe (SHA duplicado)"
                }),
                status_code=200,
                mimetype="application/json"
            )
        
        # Salvar raw
        raw_blob_name = save_raw_text(blob_service, text, sha)
        
        # Extrair metadados
        from govy.juris.metadata_extract import extract_metadata, should_auto_approve
        
        metadata_result = extract_metadata(text)
        metadata = metadata_result.to_dict()
        
        # Verificar auto-approve
        auto_approve, reason = should_auto_approve(
            metadata_result,
            text_length=len(text),
            sha_duplicate=False,
            semantic_duplicate=False
        )
        
        review_status = "APPROVED" if auto_approve else "PENDING_REVIEW"
        
        # Criar payload processado
        processed_blob_name = build_processed_blob_name(metadata, sha)
        payload = create_processed_payload(
            text=text,
            sha=sha,
            raw_blob_name=raw_blob_name,
            metadata=metadata,
            review_status=review_status,
            created_by=created_by,
            source_label=source_label
        )
        
        # Salvar processado
        save_processed(blob_service, payload, processed_blob_name)
        
        # Indexar se auto-aprovado
        kb_upsert = None
        if auto_approve:
            search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
            search_key = os.environ.get("AZURE_SEARCH_API_KEY", "")
            index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
            
            if search_key:
                kb_upsert = index_chunks_to_kb(
                    payload["chunks"],
                    search_endpoint,
                    search_key,
                    index_name
                )
        
        # Resposta
        response = {
            "status": "processed_autoapproved" if auto_approve else "pending_review",
            "source_sha": sha,
            "raw_blob_name": raw_blob_name,
            "processed_blob_name": processed_blob_name,
            "detected": metadata,
            "auto_approve_reason": reason,
            "text_length": len(text)
        }
        
        if kb_upsert:
            response["kb_upsert"] = kb_upsert
        
        return func.HttpResponse(
            json.dumps(response, ensure_ascii=False, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em kb_juris_paste")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
