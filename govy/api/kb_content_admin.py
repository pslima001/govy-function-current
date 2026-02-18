"""
govy/api/kb_content_admin.py

Endpoints de administração do KB Content Hub.
- GET /api/kb/content/list
- POST /api/kb/content/{id}/approve
- POST /api/kb/content/{id}/reject
- POST /api/kb/content/{id}/update
- POST /api/kb/content/{id}/delete

Versão: 1.0
Data: 05/02/2026
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import unquote

import azure.functions as func
from govy.utils.azure_clients import get_blob_service_client as _get_blob_svc

logger = logging.getLogger(__name__)

KB_PROCESSED_CONTAINER = os.environ.get("KB_PROCESSED_CONTAINER", "kb-processed")
KB_TRASH_CONTAINER = "kb-trash"
KB_RAW_CONTAINER = os.environ.get("KB_RAW_CONTAINER", "kb-raw")


def get_blob_service_client():
    """Obtém cliente do Blob Storage."""
    return _get_blob_svc()


def get_search_client():
    """Obtém cliente do Azure Search."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
    key = os.environ.get("AZURE_SEARCH_API_KEY", "")
    index = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
    
    return SearchClient(endpoint, index, AzureKeyCredential(key))


# =============================================================================
# LIST
# =============================================================================

def handle_kb_content_list(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/kb/content/list
    
    Query params:
    - domain: jurisprudencia (default)
    - review_status: PENDING_REVIEW, APPROVED, REJECTED (optional)
    - tribunal_family: TCU, TCE, TJ, etc. (optional)
    - limit: número máximo (default 50)
    """
    try:
        domain = req.params.get("domain", "jurisprudencia")
        review_status_filter = req.params.get("review_status")
        tribunal_family_filter = req.params.get("tribunal_family")
        limit = int(req.params.get("limit", "50"))
        
        blob_service = get_blob_service_client()
        container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
        
        # Listar blobs no prefixo
        prefix = f"{domain}/"
        items = []
        
        for blob in container.list_blobs(name_starts_with=prefix):
            if not blob.name.endswith(".json"):
                continue
            
            # Carregar metadados do blob
            blob_client = container.get_blob_client(blob.name)
            try:
                content = blob_client.download_blob().readall().decode('utf-8')
                data = json.loads(content)
            except Exception as e:
                logger.warning(f"Erro ao ler blob {blob.name}: {e}")
                continue
            
            # Filtros
            if review_status_filter:
                if data.get("review_status") != review_status_filter:
                    continue
            
            if tribunal_family_filter:
                detected = data.get("detected", {})
                if detected.get("tribunal_family") != tribunal_family_filter:
                    continue
            
            # Pular deletados
            admin = data.get("admin", {})
            if admin.get("deleted_at"):
                continue
            
            # Construir item resumido
            detected = data.get("detected", {})
            source = data.get("source", {})
            content_info = data.get("content", {})
            
            item = {
                "id": source.get("source_sha", ""),
                "processed_blob_name": blob.name,
                "review_status": data.get("review_status"),
                "tribunal_family": detected.get("tribunal_family"),
                "tribunal": detected.get("tribunal"),
                "uf": detected.get("uf"),
                "case_number_primary": detected.get("case_number_primary"),
                "year": detected.get("year"),
                "confidence": detected.get("confidence"),
                "char_count": content_info.get("char_count", 0),
                "created_at": admin.get("created_at"),
                "reject_reason": admin.get("rejection_reason"),
                "missing_elements": (data.get("quality") or {}).get("missing_elements"),

                "created_by": admin.get("created_by")
            }
            
            items.append(item)
            
            if len(items) >= limit:
                break
        
        # Ordenar por data (mais recente primeiro)
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "total": len(items),
                "items": items
            }, ensure_ascii=False, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em kb_content_list")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# =============================================================================
# APPROVE
# =============================================================================

def handle_kb_content_approve(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/kb/content/{id}/approve
    
    Aprova documento e indexa no kb-legal.
    """
    try:
        # Extrair ID do route
        doc_id = req.route_params.get("id", "")
        if not doc_id:
            return func.HttpResponse(
                json.dumps({"error": "ID não fornecido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        doc_id = unquote(doc_id)
        
        # Localizar documento
        blob_service = get_blob_service_client()
        container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
        
        # Procurar blob pelo SHA
        found_blob = None
        for blob in container.list_blobs(name_starts_with="jurisprudencia/"):
            if doc_id in blob.name and blob.name.endswith(".json"):
                found_blob = blob.name
                break
        
        if not found_blob:
            return func.HttpResponse(
                json.dumps({"error": f"Documento {doc_id} não encontrado"}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Carregar documento
        blob_client = container.get_blob_client(found_blob)
        content = blob_client.download_blob().readall().decode('utf-8')
        data = json.loads(content)
        
        # Atualizar status
        data["review_status"] = "APPROVED"
        data["admin"]["approved_at"] = datetime.now(timezone.utc).isoformat()
        
        # Salvar
        blob_client.upload_blob(
            json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            overwrite=True
        )
        
        # Indexar chunks
        chunks = data.get("chunks", [])
        kb_upsert = {"indexed": 0, "failed": 0}
        
        if chunks:
            try:
                search_client = get_search_client()
                docs = []
                for chunk in chunks:
                    doc = {
                        "chunk_id": chunk["chunk_id"],
                        "doc_type": chunk.get("doc_type", "jurisprudencia"),
                        "content": chunk.get("content", ""),
                        "citation": chunk.get("citation", ""),
                        "year": chunk.get("year", 0),
                        "authority_score": chunk.get("authority_score", 0.85),
                        "tribunal": chunk.get("tribunal"),
                        "uf": chunk.get("uf"),
                        "secao": chunk.get("secao"),
                        "procedural_stage": chunk.get("procedural_stage"),
                        "holding_outcome": chunk.get("holding_outcome"),
                        "remedy_type": chunk.get("remedy_type"),
                        "effect": chunk.get("effect"),
                        "is_current": chunk.get("is_current", True),
                        "source": "kb-approved"
                    }
                    docs.append(doc)
                
                result = search_client.upload_documents(documents=docs)
                kb_upsert["indexed"] = sum(1 for r in result if r.succeeded)
                kb_upsert["failed"] = sum(1 for r in result if not r.succeeded)
            except Exception as e:
                logger.error(f"Erro ao indexar: {e}")
                kb_upsert["error"] = str(e)
        
        return func.HttpResponse(
            json.dumps({
                "status": "approved",
                "id": doc_id,
                "processed_blob_name": found_blob,
                "kb_upsert": kb_upsert
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em kb_content_approve")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# =============================================================================
# REJECT
# =============================================================================

def handle_kb_content_reject(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/kb/content/{id}/reject
    
    Rejeita documento (não indexa).
    """
    try:
        doc_id = req.route_params.get("id", "")
        if not doc_id:
            return func.HttpResponse(
                json.dumps({"error": "ID não fornecido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        doc_id = unquote(doc_id)
        
        # Localizar documento
        blob_service = get_blob_service_client()
        container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
        
        found_blob = None
        for blob in container.list_blobs(name_starts_with="jurisprudencia/"):
            if doc_id in blob.name and blob.name.endswith(".json"):
                found_blob = blob.name
                break
        
        if not found_blob:
            return func.HttpResponse(
                json.dumps({"error": f"Documento {doc_id} não encontrado"}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Carregar e atualizar
        blob_client = container.get_blob_client(found_blob)
        content = blob_client.download_blob().readall().decode('utf-8')
        data = json.loads(content)
        
        data["review_status"] = "REJECTED"
        data["admin"]["rejected_at"] = datetime.now(timezone.utc).isoformat()
        
        try:
            body = req.get_json()
            reason = body.get("reason", "")
            if reason:
                data["admin"]["rejection_reason"] = reason
        except:
            pass
        
        # Salvar
        blob_client.upload_blob(
            json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            overwrite=True
        )
        
        return func.HttpResponse(
            json.dumps({
                "status": "rejected",
                "id": doc_id,
                "processed_blob_name": found_blob
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em kb_content_reject")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# =============================================================================
# UPDATE
# =============================================================================

def handle_kb_content_update(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/kb/content/{id}/update
    
    Atualiza metadados do documento.
    
    Body:
    {
        "patch": {
            "detected.tribunal": "TJPR",
            "admin.notes": "correção manual"
        },
        "reindex": true
    }
    """
    try:
        doc_id = req.route_params.get("id", "")
        if not doc_id:
            return func.HttpResponse(
                json.dumps({"error": "ID não fornecido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        doc_id = unquote(doc_id)
        
        try:
            body = req.get_json()
        except:
            return func.HttpResponse(
                json.dumps({"error": "JSON inválido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        patch = body.get("patch", {})
        reindex = body.get("reindex", False)
        
        # Localizar documento
        blob_service = get_blob_service_client()
        container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
        
        found_blob = None
        for blob in container.list_blobs(name_starts_with="jurisprudencia/"):
            if doc_id in blob.name and blob.name.endswith(".json"):
                found_blob = blob.name
                break
        
        if not found_blob:
            return func.HttpResponse(
                json.dumps({"error": f"Documento {doc_id} não encontrado"}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Carregar
        blob_client = container.get_blob_client(found_blob)
        content = blob_client.download_blob().readall().decode('utf-8')
        data = json.loads(content)
        
        # Aplicar patch
        for key, value in patch.items():
            parts = key.split(".")
            obj = data
            for part in parts[:-1]:
                if part not in obj:
                    obj[part] = {}
                obj = obj[part]
            obj[parts[-1]] = value
        
        data["admin"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Salvar
        blob_client.upload_blob(
            json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            overwrite=True
        )
        
        # Reindexar se solicitado
        kb_upsert = None
        if reindex and data.get("review_status") == "APPROVED":
            chunks = data.get("chunks", [])
            if chunks:
                try:
                    search_client = get_search_client()
                    
                    # Deletar chunks antigos
                    for chunk in chunks:
                        try:
                            search_client.delete_documents(documents=[{"chunk_id": chunk["chunk_id"]}])
                        except:
                            pass
                    
                    # Re-indexar
                    docs = []
                    for chunk in chunks:
                        # Atualizar chunk com dados do detected
                        detected = data.get("detected", {})
                        chunk["tribunal"] = detected.get("tribunal")
                        chunk["uf"] = detected.get("uf")
                        chunk["year"] = detected.get("year", 0)
                        
                        doc = {
                            "chunk_id": chunk["chunk_id"],
                            "doc_type": "jurisprudencia",
                            "content": chunk.get("content", ""),
                            "citation": chunk.get("citation", ""),
                            "year": chunk.get("year", 0),
                            "authority_score": chunk.get("authority_score", 0.85),
                            "tribunal": chunk.get("tribunal"),
                            "uf": chunk.get("uf"),
                            "secao": chunk.get("secao"),
                            "procedural_stage": chunk.get("procedural_stage"),
                            "is_current": True,
                            "source": "kb-updated"
                        }
                        docs.append(doc)
                    
                    result = search_client.upload_documents(documents=docs)
                    kb_upsert = {
                        "indexed": sum(1 for r in result if r.succeeded),
                        "failed": sum(1 for r in result if not r.succeeded)
                    }
                except Exception as e:
                    kb_upsert = {"error": str(e)}
        
        response = {
            "status": "updated",
            "id": doc_id,
            "processed_blob_name": found_blob,
            "patches_applied": list(patch.keys())
        }
        
        if kb_upsert:
            response["kb_upsert"] = kb_upsert
        
        return func.HttpResponse(
            json.dumps(response, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em kb_content_update")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# =============================================================================
# DELETE
# =============================================================================

def handle_kb_content_delete(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/kb/content/{id}/delete
    
    Query params:
    - mode: soft (default) ou hard
    
    Soft delete: move para kb-trash, remove do search
    Hard delete: apaga permanentemente (requer admin)
    """
    try:
        doc_id = req.route_params.get("id", "")
        if not doc_id:
            return func.HttpResponse(
                json.dumps({"error": "ID não fornecido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        doc_id = unquote(doc_id)
        mode = req.params.get("mode", "soft")
        
        # Validar modo
        if mode not in ["soft", "hard"]:
            return func.HttpResponse(
                json.dumps({"error": "Mode deve ser 'soft' ou 'hard'"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Hard delete requer token admin
        if mode == "hard":
            admin_token = req.headers.get("X-Admin-Token", "")
            expected_token = os.environ.get("KB_ADMIN_TOKEN", "")
            if not expected_token or admin_token != expected_token:
                return func.HttpResponse(
                    json.dumps({"error": "Hard delete requer token admin"}),
                    status_code=403,
                    mimetype="application/json"
                )
        
        # Localizar documento
        blob_service = get_blob_service_client()
        processed_container = blob_service.get_container_client(KB_PROCESSED_CONTAINER)
        
        found_blob = None
        for blob in processed_container.list_blobs(name_starts_with="jurisprudencia/"):
            if doc_id in blob.name and blob.name.endswith(".json"):
                found_blob = blob.name
                break
        
        if not found_blob:
            return func.HttpResponse(
                json.dumps({"error": f"Documento {doc_id} não encontrado"}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Carregar documento
        blob_client = processed_container.get_blob_client(found_blob)
        content = blob_client.download_blob().readall().decode('utf-8')
        data = json.loads(content)
        
        # Remover do Azure Search
        chunks = data.get("chunks", [])
        search_deleted = 0
        try:
            search_client = get_search_client()
            for chunk in chunks:
                try:
                    search_client.delete_documents(documents=[{"chunk_id": chunk["chunk_id"]}])
                    search_deleted += 1
                except:
                    pass
        except Exception as e:
            logger.warning(f"Erro ao remover do search: {e}")
        
        if mode == "soft":
            # Marcar como deletado
            data["admin"]["deleted_at"] = datetime.now(timezone.utc).isoformat()
            data["review_status"] = "DELETED"
            
            # Mover para kb-trash
            trash_container = blob_service.get_container_client(KB_TRASH_CONTAINER)
            try:
                trash_container.create_container()
            except:
                pass
            
            trash_blob_name = f"deleted/{found_blob}"
            trash_blob = trash_container.get_blob_client(trash_blob_name)
            trash_blob.upload_blob(
                json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                overwrite=True
            )
            
            # Deletar do processed
            blob_client.delete_blob()
            
            # Também mover raw se existir
            source_info = data.get("source", {})
            raw_blob_name = source_info.get("raw_blob_name")
            if raw_blob_name:
                try:
                    raw_container = blob_service.get_container_client(KB_RAW_CONTAINER)
                    raw_blob = raw_container.get_blob_client(raw_blob_name)
                    if raw_blob.exists():
                        raw_content = raw_blob.download_blob().readall()
                        trash_raw = trash_container.get_blob_client(f"deleted/{raw_blob_name}")
                        trash_raw.upload_blob(raw_content, overwrite=True)
                        raw_blob.delete_blob()
                except Exception as e:
                    logger.warning(f"Erro ao mover raw: {e}")
            
            return func.HttpResponse(
                json.dumps({
                    "status": "soft_deleted",
                    "id": doc_id,
                    "moved_to": f"kb-trash/{trash_blob_name}",
                    "search_removed": search_deleted
                }),
                status_code=200,
                mimetype="application/json"
            )
        
        else:  # hard delete
            # Deletar permanentemente
            blob_client.delete_blob()
            
            # Deletar raw
            source_info = data.get("source", {})
            raw_blob_name = source_info.get("raw_blob_name")
            if raw_blob_name:
                try:
                    raw_container = blob_service.get_container_client(KB_RAW_CONTAINER)
                    raw_blob = raw_container.get_blob_client(raw_blob_name)
                    if raw_blob.exists():
                        raw_blob.delete_blob()
                except:
                    pass
            
            return func.HttpResponse(
                json.dumps({
                    "status": "hard_deleted",
                    "id": doc_id,
                    "search_removed": search_deleted
                }),
                status_code=200,
                mimetype="application/json"
            )
        
    except Exception as e:
        logger.exception("Erro em kb_content_delete")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
