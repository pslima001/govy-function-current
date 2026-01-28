# govy/api/kb_index_upsert.py
"""
Endpoint para indexar chunks na Knowledge Base Juridica
COM GATES DE VALIDACAO para jurisprudencia
Versao: 2.0 - Adiciona validacao effect/region
"""
import os
import json
import logging
import azure.functions as func
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTES E VALIDACAO
# ============================================================

REQUIRED_FIELDS = ["chunk_id", "doc_type", "content"]

UF_TO_REGION = {
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    "DF": "CENTRO_OESTE", "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE",
    "AC": "NORTE", "AM": "NORTE", "AP": "NORTE", "PA": "NORTE", 
    "RO": "NORTE", "RR": "NORTE", "TO": "NORTE"
}

VALID_REGIONS = {"SUDESTE", "SUL", "NORDESTE", "CENTRO_OESTE", "NORTE"}
VALID_EFFECTS = {"FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"}
VALID_TRIBUNALS = {"TCU", "TCE"}


def validate_jurisprudencia(chunk: dict) -> List[str]:
    """Valida chunk de jurisprudencia com gates rigorosos."""
    errors = []
    
    # effect obrigatorio
    effect = chunk.get("effect")
    if not effect:
        errors.append("Campo 'effect' obrigatorio para doc_type=jurisprudencia")
    elif effect not in VALID_EFFECTS:
        errors.append(f"Campo 'effect' invalido: {effect}. Aceitos: {list(VALID_EFFECTS)}")
    
    # tribunal obrigatorio
    tribunal = chunk.get("tribunal")
    if not tribunal:
        errors.append("Campo 'tribunal' obrigatorio para doc_type=jurisprudencia")
    elif tribunal not in VALID_TRIBUNALS:
        errors.append(f"Campo 'tribunal' invalido: {tribunal}. Aceitos: {list(VALID_TRIBUNALS)}")
    else:
        uf = chunk.get("uf")
        region = chunk.get("region")
        
        if tribunal == "TCE":
            if not uf:
                errors.append("Campo 'uf' obrigatorio para tribunal=TCE")
            elif uf.upper() not in UF_TO_REGION:
                errors.append(f"Campo 'uf' invalido: {uf}")
            
            if not region:
                errors.append("Campo 'region' obrigatorio para tribunal=TCE")
            elif region not in VALID_REGIONS:
                errors.append(f"Campo 'region' invalido: {region}. Aceitos: {list(VALID_REGIONS)}")
            
            if uf and region:
                expected = UF_TO_REGION.get(uf.upper())
                if expected and expected != region:
                    errors.append(f"UF {uf} deveria ter region={expected}, nao {region}")
        
        elif tribunal == "TCU":
            if uf:
                errors.append("Campo 'uf' deve ser null para tribunal=TCU")
            if region:
                errors.append("Campo 'region' deve ser null para tribunal=TCU")
    
    return errors


def validate_chunk(chunk: dict, index: int) -> List[str]:
    """Valida chunk generico + gates especificos por doc_type."""
    errors = []
    
    # Campos obrigatorios basicos
    for field in REQUIRED_FIELDS:
        if not chunk.get(field):
            errors.append(f"[{index}] Campo obrigatorio ausente: {field}")
    
    if errors:
        return errors
    
    # Gates especificos para jurisprudencia
    doc_type = chunk.get("doc_type", "").lower()
    if doc_type == "jurisprudencia":
        juris_errors = validate_jurisprudencia(chunk)
        errors.extend([f"[{index}] {e}" for e in juris_errors])
    
    return errors


def generate_embedding(text: str) -> List[float]:
    """Gera embedding usando OpenAI."""
    import openai
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao configurada")
    
    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def get_search_client():
    """Retorna cliente do Azure AI Search."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
    
    if not endpoint or not api_key:
        raise ValueError("AZURE_SEARCH_ENDPOINT ou AZURE_SEARCH_API_KEY nao configurados")
    
    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handler principal do endpoint upsert."""
    
    # CORS
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "JSON invalido"}),
            status_code=400,
            mimetype="application/json"
        )
    
    chunks = body.get("chunks", [])
    generate_embeddings = body.get("generate_embeddings", True)
    
    if not chunks:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Lista de chunks vazia"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # ============================================================
    # VALIDACAO COM GATES
    # ============================================================
    validation_errors = []
    valid_chunks = []
    
    for i, chunk in enumerate(chunks):
        errors = validate_chunk(chunk, i)
        if errors:
            validation_errors.extend(errors)
        else:
            valid_chunks.append(chunk)
    
    # Se houver erros de validacao, NAO indexar nenhum
    if validation_errors:
        return func.HttpResponse(
            json.dumps({
                "status": "validation_failed",
                "message": "Chunks rejeitados por falha na validacao",
                "validation_errors": validation_errors,
                "total_received": len(chunks),
                "total_valid": len(valid_chunks),
                "total_rejected": len(chunks) - len(valid_chunks)
            }),
            status_code=400,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    # ============================================================
    # INDEXACAO
    # ============================================================
    try:
        search_client = get_search_client()
    except Exception as e:
        logger.error(f"Erro ao conectar Azure Search: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Erro conexao Azure Search: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    documents = []
    embedding_errors = []
    
    for i, chunk in enumerate(valid_chunks):
        doc = {
            "chunk_id": chunk["chunk_id"],
            "doc_type": chunk.get("doc_type"),
            "source": chunk.get("source"),
            "tribunal": chunk.get("tribunal"),
            "uf": chunk.get("uf"),
            "region": chunk.get("region"),
            "effect": chunk.get("effect"),
            "title": chunk.get("title"),
            "content": chunk.get("content"),
            "citation": chunk.get("citation"),
            "year": chunk.get("year"),
            "authority_score": chunk.get("authority_score", 0.5),
            "is_current": chunk.get("is_current", True)
        }
        
        # Gerar embedding
        if generate_embeddings:
            try:
                text_for_embedding = f"{doc.get('title', '')} {doc.get('content', '')}"
                doc["embedding"] = generate_embedding(text_for_embedding)
            except Exception as e:
                embedding_errors.append({"index": i, "chunk_id": chunk["chunk_id"], "error": str(e)})
                continue
        elif chunk.get("embedding"):
            doc["embedding"] = chunk["embedding"]
        
        documents.append(doc)
    
    if not documents:
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Nenhum documento para indexar apos geracao de embeddings",
                "embedding_errors": embedding_errors
            }),
            status_code=400,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    # Upload para Azure Search
    try:
        result = search_client.upload_documents(documents=documents)
        
        succeeded = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        errors = [{"key": r.key, "error": r.error_message} for r in result if not r.succeeded]
        
        status = "success" if failed == 0 else "partial"
        
        return func.HttpResponse(
            json.dumps({
                "status": status,
                "indexed": succeeded,
                "failed": failed,
                "errors": errors,
                "embedding_errors": embedding_errors
            }),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error(f"Erro ao indexar documentos: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Erro ao indexar: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
