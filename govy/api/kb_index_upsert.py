"""
GOVY - Handler do Endpoint /api/kb/index/upsert
SPEC 1.3 (Golden Path) - Knowledge Base Juridica

Indexa chunks no Azure AI Search com validacao dos novos campos:
- secao (obrigatorio para jurisprudencia)
- procedural_stage
- holding_outcome
- remedy_type
- claim_pattern
- effect
- region (derivado de UF para TCE, null para TCU)
"""

# ===========================================================================
# GOLDEN PATH - DO NOT CHANGE WITHOUT SPEC UPDATE
# SPEC: SPEC_KB_PIPELINE_v1.3.md
# ===========================================================================

KB_PIPELINE_VERSION = "1.3"

import os
import json
import logging
import uuid
from typing import Dict, Any, List, Optional
import azure.functions as func
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import OpenAI

# Fonte unica de normalizacao (definitivo)
try:
    from govy.utils.juris_constants import normalize_chunk_for_upsert
except ImportError as e:
    import logging
    logging.warning(f"Falha ao importar normalize_chunk_for_upsert: {e}")
    def normalize_chunk_for_upsert(chunk, tribunal=None):
        return chunk  # Fallback: retorna chunk sem modificar

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURACAO
# =============================================================================

AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# =============================================================================
# CONSTANTES E VALIDACAO - SPEC 1.3 (Golden Path)
# =============================================================================

# Mapeamento UF -> Region (IBGE)
UF_TO_REGION = {
    # SUDESTE
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    # SUL
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    # NORDESTE
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    # CENTRO_OESTE
    "DF": "CENTRO_OESTE", "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE",
    # NORTE
    "AC": "NORTE", "AM": "NORTE", "AP": "NORTE", "PA": "NORTE",
    "RO": "NORTE", "RR": "NORTE", "TO": "NORTE",
}

# Enums validos
VALID_DOC_TYPES = ["jurisprudencia", "lei", "doutrina", "edital"]
VALID_TRIBUNALS = ["TCU", "TCE"]
VALID_SECOES = ["tese", "vital", "fundamento_legal", "limites", "contexto_minimo"]
VALID_PROCEDURAL_STAGES = ["EDITAL", "DISPUTA", "JULGAMENTO", "HABILITACAO", "CONTRATACAO", "EXECUCAO", "PAGAMENTO", "SANCIONAMENTO", "NAO_CLARO"]
VALID_HOLDING_OUTCOMES = ["MANTEVE", "AFASTOU", "DETERMINOU_AJUSTE", "ANULOU", "NAO_CLARO"]
VALID_REMEDY_TYPES = ["IMPUGNACAO", "RECURSO", "CONTRARRAZOES", "REPRESENTACAO", "DENUNCIA", "ORIENTACAO_GERAL", "NAO_CLARO"]
VALID_EFFECTS = ["FLEXIBILIZA", "RIGORIZA", "CONDICIONAL", "NAO_CLARO"]

# Campos obrigatorios base
REQUIRED_FIELDS = ["chunk_id", "doc_type", "content"]

# Campos obrigatorios para jurisprudencia
REQUIRED_FIELDS_JURISPRUDENCIA = ["chunk_id", "doc_type", "content", "tribunal", "secao", "effect"]


def validate_chunk(chunk: Dict, index: int) -> List[str]:
    """
    Valida um chunk conforme SPEC 1.3 (Golden Path).
    
    Retorna lista de erros (vazia se valido).
    """
    errors = []
    
    # Campos obrigatorios base
    for field in REQUIRED_FIELDS:
        if field not in chunk or not chunk[field]:
            errors.append(f"Chunk {index}: Campo obrigatorio faltando: {field}")
    
    if errors:
        return errors  # Se faltam campos base, retorna logo
    
    doc_type = chunk.get("doc_type")
    tribunal = chunk.get("tribunal")
    uf = chunk.get("uf")
    
    # Valida doc_type
    if doc_type and doc_type not in VALID_DOC_TYPES:
        errors.append(f"Chunk {index}: doc_type invalido: {doc_type}. Validos: {VALID_DOC_TYPES}")
    
    # Regras especificas para jurisprudencia
    if doc_type == "jurisprudencia":
        # secao obrigatorio
        secao = chunk.get("secao")
        if not secao:
            errors.append(f"Chunk {index}: secao e obrigatorio para jurisprudencia")
        elif secao not in VALID_SECOES:
            errors.append(f"Chunk {index}: secao invalida: {secao}. Validas: {VALID_SECOES}")
        
        # tribunal obrigatorio
        if not tribunal:
            errors.append(f"Chunk {index}: tribunal e obrigatorio para jurisprudencia")
        elif tribunal not in VALID_TRIBUNALS:
            errors.append(f"Chunk {index}: tribunal invalido: {tribunal}. Validos: {VALID_TRIBUNALS}")
        
        # effect obrigatorio para jurisprudencia
        effect = chunk.get("effect")
        if not effect:
            errors.append(f"Chunk {index}: effect e obrigatorio para jurisprudencia")
        elif effect not in VALID_EFFECTS:
            errors.append(f"Chunk {index}: effect invalido: {effect}. Validos: {VALID_EFFECTS}")
        
        # Regra TCU vs TCE
        if tribunal == "TCU":
            if uf is not None and uf != "":
                errors.append(f"Chunk {index}: TCU deve ter uf=null (recebeu: {uf})")
        elif tribunal == "TCE":
            if not uf:
                errors.append(f"Chunk {index}: TCE deve ter uf preenchido")
            elif uf not in UF_TO_REGION:
                errors.append(f"Chunk {index}: UF invalida: {uf}")
        
        # Valida enums opcionais (se preenchidos)
        procedural_stage = chunk.get("procedural_stage")
        if procedural_stage and procedural_stage not in VALID_PROCEDURAL_STAGES:
            errors.append(f"Chunk {index}: procedural_stage invalido: {procedural_stage}")
        
        holding_outcome = chunk.get("holding_outcome")
        if holding_outcome and holding_outcome not in VALID_HOLDING_OUTCOMES:
            errors.append(f"Chunk {index}: holding_outcome invalido: {holding_outcome}")
        
        remedy_type = chunk.get("remedy_type")
        if remedy_type and remedy_type not in VALID_REMEDY_TYPES:
            errors.append(f"Chunk {index}: remedy_type invalido: {remedy_type}")
    
    return errors


def prepare_chunk_for_index(chunk: Dict) -> Dict:
    """
    Prepara chunk para indexacao no Azure Search.
    - Gera chunk_id se nao existir
    - Deriva region de UF para TCE
    - Garante region=null para TCU
    - Remove campos nao indexaveis
    """
    doc = chunk.copy()
    
    # Gera chunk_id se nao existir
    if not doc.get("chunk_id"):
        doc["chunk_id"] = str(uuid.uuid4())
    
    # Deriva region
    tribunal = doc.get("tribunal")
    uf = doc.get("uf")
    
    if tribunal == "TCU":
        doc["uf"] = None
        doc["region"] = None
    elif tribunal == "TCE" and uf:
        doc["region"] = UF_TO_REGION.get(uf)
    
    # Garante que campos nulos sejam None (nao string vazia)
    for field in ["uf", "region", "fundamento_legal", "limites", "contexto_minimo"]:
        if doc.get(field) == "":
            doc[field] = None
    
    # Campos do indice (SPEC 1.3 (Golden Path) + governanca v1)
    index_fields = [
        "chunk_id", "doc_type", "source", "tribunal", "uf", "region",
        "title", "content", "citation", "year", "authority_score", "is_current",
        "effect", "secao", "procedural_stage", "holding_outcome", "remedy_type", "claim_pattern",
        "embedding",
        # Governanca de citabilidade (v1 - 2026-02-27)
        "is_citable", "citable_reason", "source_work",
    ]
    
    # Remove campos que nao estao no indice
    return {k: v for k, v in doc.items() if k in index_fields}


def generate_embedding(text: str) -> List[float]:
    """Gera embedding usando OpenAI text-embedding-3-small."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    
    return response.data[0].embedding


def index_chunks(chunks: List[Dict], generate_embeddings: bool = True) -> Dict[str, Any]:
    """
    Indexa lista de chunks no Azure Search.
    
    Args:
        chunks: Lista de chunks validados
        generate_embeddings: Se True, gera embeddings para cada chunk
        
    Returns:
        Dict com status, indexed, failed, errors
    """
    if not AZURE_SEARCH_API_KEY:
        return {"status": "error", "error": "AZURE_SEARCH_API_KEY nao configurada"}
    
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
    )
    
    documents = []
    errors = []
    
    for i, chunk in enumerate(chunks):
        try:
            doc = prepare_chunk_for_index(chunk)
            
            # Gera embedding se solicitado
            if generate_embeddings and doc.get("content"):
                doc["embedding"] = generate_embedding(doc["content"])
            
            documents.append(doc)
            
        except Exception as e:
            errors.append({"index": i, "chunk_id": chunk.get("chunk_id"), "error": str(e)})
    
    if not documents:
        return {
            "status": "error",
            "indexed": 0,
            "failed": len(chunks),
            "errors": errors
        }
    
    # Upload para Azure Search
    try:
        result = search_client.upload_documents(documents)
        
        indexed = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        
        # Coleta erros do Azure Search
        for r in result:
            if not r.succeeded:
                errors.append({"chunk_id": r.key, "error": r.error_message})
        
        status = "success" if failed == 0 else "partial"
        
        return {
            "status": status,
            "indexed": indexed,
            "failed": failed,
            "errors": errors
        }
        
    except Exception as e:
        logger.exception(f"Erro ao indexar: {e}")
        return {
            "status": "error",
            "indexed": 0,
            "failed": len(documents),
            "errors": [{"error": str(e)}]
        }


# =============================================================================
# HANDLER PRINCIPAL
# =============================================================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/kb/index/upsert
    
    Indexa chunks no Azure AI Search.
    
    Request:
    {
        "chunks": [
            {
                "chunk_id": "uuid",
                "doc_type": "jurisprudencia",
                "tribunal": "TCU",
                "uf": null,
                "secao": "vital",
                "effect": "FLEXIBILIZA",
                "procedural_stage": "HABILITACAO",
                "holding_outcome": "AFASTOU",
                "remedy_type": "REPRESENTACAO",
                "claim_pattern": "exigencia de atestado",
                "title": "...",
                "content": "...",
                "citation": "...",
                "year": 2025,
                "authority_score": 0.90,
                "is_current": true
            }
        ],
        "generate_embeddings": true
    }
    
    Response:
    {
        "status": "success" | "partial" | "error",
        "indexed": N,
        "failed": N,
        "errors": [],
        "validation_errors": []
    }
    """
    
    # CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json"
    }
    
    try:
        # Parse request
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "Invalid JSON"}),
                status_code=200,  # Definitivo: nao quebra pipeline
                headers=cors_headers
            )
        
        chunks = body.get("chunks", [])
        generate_embeddings = body.get("generate_embeddings", True)
        
        if not chunks:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "Nenhum chunk fornecido"}),
                status_code=200,  # Definitivo: nao quebra pipeline
                headers=cors_headers
            )
        
        # Validar todos os chunks
        validation_errors = []
        valid_chunks = []
        
        for i, chunk in enumerate(chunks):
            # Normalizar/clamp ANTES de validar
            chunk = normalize_chunk_for_upsert(chunk, tribunal=chunk.get("tribunal"))
            errors = validate_chunk(chunk, i)
            if errors:
                validation_errors.extend(errors)
            else:
                valid_chunks.append(chunk)
        
        # Se nenhum chunk valido, retorna erro
        if not valid_chunks:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "indexed": 0,
                    "failed": len(chunks),
                    "errors": [],
                    "validation_errors": validation_errors
                }),
                status_code=200,  # Definitivo: nao quebra pipeline
                headers=cors_headers
            )
        
        # Indexar chunks validos
        result = index_chunks(valid_chunks, generate_embeddings)
        
        # Adiciona validation_errors ao resultado
        result["validation_errors"] = validation_errors
        result["total_received"] = len(chunks)
        result["total_valid"] = len(valid_chunks)
        
        status_code = 200 if result["status"] != "error" else 500
        
        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=status_code,
            headers=cors_headers
        )
        
    except Exception as e:
        logger.exception(f"Erro no upsert: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "error": str(e)}),
            status_code=500,
            headers=cors_headers
        )

