# govy/api/dicionario_api.py
"""
API para gerenciar dicionrio de termos - v1

Endpoints:
- GET  /api/dicionario        -> Lista termos (com paginao)
- POST /api/dicionario        -> Adiciona termos
- DELETE /api/dicionario      -> Remove termos
"""
import os
import re
import json
import logging
import unicodedata
import azure.functions as func
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

CONTAINER_NAME = "govy-config"
BLOB_NAME = "dicionario/termos.json"


def normalizar_texto(texto: str) -> str:
    """Normaliza texto: remove acentos, lowercase, limpa caracteres especiais."""
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def carregar_dicionario(blob_service: BlobServiceClient) -> dict:
    """Carrega dicionrio do Azure Blob."""
    try:
        container = blob_service.get_container_client(CONTAINER_NAME)
        blob = container.get_blob_client(BLOB_NAME)
        content = blob.download_blob().readall()
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Erro ao carregar dicionrio: {e}")
        return {"version": "1.0", "termos": [], "total": 0}


def salvar_dicionario(blob_service: BlobServiceClient, data: dict) -> bool:
    """Salva dicionrio no Azure Blob."""
    try:
        container = blob_service.get_container_client(CONTAINER_NAME)
        blob = container.get_blob_client(BLOB_NAME)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        blob.upload_blob(content, overwrite=True)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar dicionrio: {e}")
        return False


def handle_dicionario(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handler principal do endpoint /api/dicionario
    
    GET  - Lista termos (?search=termo&page=1&limit=100&stats=true)
    POST - Adiciona termos (body: {"termos": ["termo1", "termo2"]})
    DELETE - Remove termos (body: {"termos": ["termo1", "termo2"]})
    """
    
    logger.info(f"=== DICIONARIO API - {req.method} ===")
    
    try:
        conn_str = os.environ.get("AzureWebJobsStorage")
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        data = carregar_dicionario(blob_service)
        termos_set = set(data.get("termos", []))
        
        # ========== GET - Listar/Buscar ==========
        if req.method == "GET":
            # Apenas estatsticas
            if req.params.get("stats") == "true":
                return func.HttpResponse(
                    json.dumps({
                        "success": True,
                        "total": len(termos_set),
                        "version": data.get("version", "1.0")
                    }),
                    status_code=200,
                    mimetype="application/json"
                )
            
            termos_list = list(termos_set)
            
            # Filtro de busca
            search = req.params.get("search", "").strip().lower()
            if search:
                termos_list = [t for t in termos_list if search in t]
            
            # Paginao
            page = int(req.params.get("page", 1))
            limit = min(int(req.params.get("limit", 100)), 1000)
            
            termos_sorted = sorted(termos_list)
            total = len(termos_sorted)
            start = (page - 1) * limit
            end = start + limit
            termos_pagina = termos_sorted[start:end]
            
            return func.HttpResponse(
                json.dumps({
                    "success": True,
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit,
                    "termos": termos_pagina
                }, ensure_ascii=False),
                status_code=200,
                mimetype="application/json"
            )
        
        # ========== POST - Adicionar ==========
        elif req.method == "POST":
            body = req.get_json()
            novos_termos = body.get("termos", [])
            
            if not novos_termos:
                return func.HttpResponse(
                    json.dumps({"success": False, "error": "Campo 'termos' obrigatrio"}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            # Normalizar e adicionar
            adicionados = []
            for termo in novos_termos:
                termo_norm = normalizar_texto(termo)
                if termo_norm and len(termo_norm) >= 3 and termo_norm not in termos_set:
                    termos_set.add(termo_norm)
                    adicionados.append(termo_norm)
            
            # Salvar
            data["termos"] = list(termos_set)
            data["total"] = len(termos_set)
            
            if salvar_dicionario(blob_service, data):
                return func.HttpResponse(
                    json.dumps({
                        "success": True,
                        "adicionados": len(adicionados),
                        "termos_adicionados": adicionados,
                        "total": len(termos_set)
                    }, ensure_ascii=False),
                    status_code=200,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({"success": False, "error": "Falha ao salvar"}),
                    status_code=500,
                    mimetype="application/json"
                )
        
        # ========== DELETE - Remover ==========
        elif req.method == "DELETE":
            body = req.get_json()
            termos_remover = body.get("termos", [])
            
            if not termos_remover:
                return func.HttpResponse(
                    json.dumps({"success": False, "error": "Campo 'termos' obrigatrio"}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            # Normalizar e remover
            removidos = []
            for termo in termos_remover:
                termo_norm = normalizar_texto(termo)
                if termo_norm in termos_set:
                    termos_set.remove(termo_norm)
                    removidos.append(termo_norm)
            
            # Salvar
            data["termos"] = list(termos_set)
            data["total"] = len(termos_set)
            
            if salvar_dicionario(blob_service, data):
                return func.HttpResponse(
                    json.dumps({
                        "success": True,
                        "removidos": len(removidos),
                        "termos_removidos": removidos,
                        "total": len(termos_set)
                    }, ensure_ascii=False),
                    status_code=200,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({"success": False, "error": "Falha ao salvar"}),
                    status_code=500,
                    mimetype="application/json"
                )
        
        else:
            return func.HttpResponse(
                json.dumps({"success": False, "error": f"Mtodo {req.method} no suportado"}),
                status_code=405,
                mimetype="application/json"
            )
    
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
