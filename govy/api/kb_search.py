# govy/api/kb_search.py
"""
Endpoint de busca na Knowledge Base Juridica
COM FALLBACK SEQUENCIAL (4 etapas) + EFFECT
Versao: 2.0
"""
import os
import json
import logging
import azure.functions as func
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTES
# ============================================================

UF_TO_REGION = {
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    "DF": "CENTRO_OESTE", "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE",
    "AC": "NORTE", "AM": "NORTE", "AP": "NORTE", "PA": "NORTE", 
    "RO": "NORTE", "RR": "NORTE", "TO": "NORTE"
}

SCENARIO_TO_EFFECT = {
    1: "FLEXIBILIZA",
    2: "RIGORIZA",
    3: "FLEXIBILIZA",
    4: "RIGORIZA",
}


def get_region(uf: str) -> Optional[str]:
    """Retorna a regiao para uma UF."""
    if not uf:
        return None
    return UF_TO_REGION.get(uf.upper())


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


def build_filter(doc_type: str, effect: str, tribunal: str = None, uf: str = None, 
                 region: str = None, exclude_uf: str = None, exclude_region: str = None) -> str:
    """Constroi filtro OData para Azure Search."""
    filters = []
    
    filters.append(f"doc_type eq '{doc_type}'")
    filters.append(f"effect eq '{effect}'")
    
    if tribunal:
        filters.append(f"tribunal eq '{tribunal}'")
    
    if uf:
        filters.append(f"uf eq '{uf}'")
    
    if region:
        filters.append(f"region eq '{region}'")
    
    if exclude_uf:
        filters.append(f"uf ne '{exclude_uf}'")
    
    if exclude_region:
        filters.append(f"region ne '{exclude_region}'")
    
    return " and ".join(filters)


def execute_search(search_client, query: str, query_vector: List[float], 
                   filter_str: str, top_k: int, use_semantic: bool) -> Tuple[List[Dict], Dict]:
    """Executa busca hibrida no Azure Search."""
    from azure.search.documents.models import VectorizedQuery
    
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="embedding"
    )
    
    search_params = {
        "search_text": query,
        "vector_queries": [vector_query],
        "filter": filter_str,
        "top": top_k,
        "select": ["chunk_id", "doc_type", "source", "tribunal", "uf", "region", 
                   "effect", "title", "content", "citation", "year", "authority_score", "is_current"]
    }
    
    if use_semantic:
        search_params["query_type"] = "semantic"
        search_params["semantic_configuration_name"] = "kb-legal-semantic"
    
    results = search_client.search(**search_params)
    
    items = []
    debug_info = {"filter": filter_str, "top_k": top_k}
    
    for result in results:
        item = {
            "chunk_id": result.get("chunk_id"),
            "doc_type": result.get("doc_type"),
            "source": result.get("source"),
            "tribunal": result.get("tribunal"),
            "uf": result.get("uf"),
            "region": result.get("region"),
            "effect": result.get("effect"),
            "title": result.get("title"),
            "content": result.get("content"),
            "citation": result.get("citation"),
            "year": result.get("year"),
            "authority_score": result.get("authority_score"),
            "is_current": result.get("is_current"),
            "search_score": result.get("@search.score"),
            "reranker_score": result.get("@search.reranker_score")
        }
        items.append(item)
    
    if items:
        debug_info["top1_score"] = items[0].get("search_score")
    
    return items, debug_info


def fallback_search(search_client, query: str, query_vector: List[float],
                    user_uf: str, desired_effect: str, top_k: int, 
                    use_semantic: bool) -> Tuple[List[Dict], str, List[Dict]]:
    """
    Executa busca com fallback sequencial de 4 etapas.
    
    Etapas PASSADA 1 (desired_effect):
    1. TCE da UF do usuario
    2. TCU
    3. TCE da mesma regiao
    4. TCE de outras regioes
    
    Retorna: (resultados, winner_stage, debug_stages)
    """
    user_region = get_region(user_uf)
    debug_stages = []
    
    # ============================================================
    # ETAPA 1: TCE da UF do usuario
    # ============================================================
    if user_uf:
        filter_str = build_filter(
            doc_type="jurisprudencia",
            effect=desired_effect,
            tribunal="TCE",
            uf=user_uf.upper()
        )
        results, debug = execute_search(
            search_client, query, query_vector, filter_str, top_k, use_semantic
        )
        debug["stage"] = "TCE_UF"
        debug["stage_description"] = f"TCE da UF {user_uf}"
        debug_stages.append(debug)
        
        if results:
            return results, "TCE_UF", debug_stages
    
    # ============================================================
    # ETAPA 2: TCU
    # ============================================================
    filter_str = build_filter(
        doc_type="jurisprudencia",
        effect=desired_effect,
        tribunal="TCU"
    )
    results, debug = execute_search(
        search_client, query, query_vector, filter_str, top_k, use_semantic
    )
    debug["stage"] = "TCU"
    debug["stage_description"] = "TCU (federal)"
    debug_stages.append(debug)
    
    if results:
        return results, "TCU", debug_stages
    
    # ============================================================
    # ETAPA 3: TCE da mesma regiao
    # ============================================================
    if user_region and user_uf:
        filter_str = build_filter(
            doc_type="jurisprudencia",
            effect=desired_effect,
            tribunal="TCE",
            region=user_region,
            exclude_uf=user_uf.upper()
        )
        results, debug = execute_search(
            search_client, query, query_vector, filter_str, top_k, use_semantic
        )
        debug["stage"] = "TCE_REGION"
        debug["stage_description"] = f"TCE da regiao {user_region} (exceto {user_uf})"
        debug_stages.append(debug)
        
        if results:
            return results, "TCE_REGION", debug_stages
    
    # ============================================================
    # ETAPA 4: TCE de outras regioes
    # ============================================================
    if user_region:
        filter_str = build_filter(
            doc_type="jurisprudencia",
            effect=desired_effect,
            tribunal="TCE",
            exclude_region=user_region
        )
    else:
        filter_str = build_filter(
            doc_type="jurisprudencia",
            effect=desired_effect,
            tribunal="TCE"
        )
    
    results, debug = execute_search(
        search_client, query, query_vector, filter_str, top_k, use_semantic
    )
    debug["stage"] = "TCE_BR"
    debug["stage_description"] = "TCE de outras regioes"
    debug_stages.append(debug)
    
    if results:
        return results, "TCE_BR", debug_stages
    
    return [], "NONE", debug_stages


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handler principal do endpoint search."""
    
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
    
    query = body.get("query")
    if not query:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Campo 'query' obrigatorio"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Parametros
    top_k = body.get("top_k", 8)
    doc_types = body.get("doc_type", ["jurisprudencia"])
    user_uf = body.get("user_uf")
    scenario = body.get("scenario")
    use_semantic = body.get("use_semantic", True)
    use_vector = body.get("use_vector", True)
    debug_mode = body.get("debug", False)
    
    # Filtros legados (para compatibilidade)
    filters = body.get("filters", {})
    
    try:
        search_client = get_search_client()
    except Exception as e:
        logger.error(f"Erro ao conectar Azure Search: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Erro conexao: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    try:
        # Gerar embedding da query
        query_vector = generate_embedding(query) if use_vector else []
        
        # ============================================================
        # MODO FALLBACK SEQUENCIAL (quando scenario informado)
        # ============================================================
        if scenario is not None and "jurisprudencia" in doc_types:
            desired_effect = SCENARIO_TO_EFFECT.get(scenario)
            if not desired_effect:
                return func.HttpResponse(
                    json.dumps({
                        "status": "error", 
                        "message": f"Scenario invalido: {scenario}. Aceitos: 1,2,3,4"
                    }),
                    status_code=400,
                    mimetype="application/json",
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            
            debug_info = {
                "scenario_used": scenario,
                "desired_effect_used": desired_effect,
                "user_uf": user_uf,
                "user_region": get_region(user_uf) if user_uf else None,
                "stages": []
            }
            
            # PASSADA 1: com desired_effect
            results, winner_stage, stages = fallback_search(
                search_client, query, query_vector, user_uf, 
                desired_effect, top_k, use_semantic
            )
            debug_info["stages"].extend(stages)
            debug_info["passada1_winner"] = winner_stage
            
            # PASSADA 2: se nao achou nada, tentar com CONDICIONAL
            if not results and desired_effect != "CONDICIONAL":
                logger.info("Passada 1 vazia, tentando CONDICIONAL")
                results, winner_stage, stages = fallback_search(
                    search_client, query, query_vector, user_uf,
                    "CONDICIONAL", top_k, use_semantic
                )
                debug_info["stages"].extend(stages)
                debug_info["passada2_winner"] = winner_stage
                debug_info["used_condicional_fallback"] = True
            else:
                debug_info["used_condicional_fallback"] = False
            
            debug_info["winner_stage"] = winner_stage if results else "NONE"
            
            response = {
                "status": "success",
                "query": query,
                "total": len(results),
                "results": results
            }
            
            if debug_mode:
                response["debug"] = debug_info
            
            return func.HttpResponse(
                json.dumps(response),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        # ============================================================
        # MODO SIMPLES (sem scenario - compatibilidade)
        # ============================================================
        from azure.search.documents.models import VectorizedQuery
        
        # Construir filtro simples
        filter_parts = []
        
        if filters.get("doc_type"):
            doc_type_filters = [f"doc_type eq '{dt}'" for dt in filters["doc_type"]]
            filter_parts.append(f"({' or '.join(doc_type_filters)})")
        elif doc_types:
            doc_type_filters = [f"doc_type eq '{dt}'" for dt in doc_types]
            filter_parts.append(f"({' or '.join(doc_type_filters)})")
        
        if filters.get("tribunal"):
            tribunal_filters = [f"tribunal eq '{t}'" for t in filters["tribunal"]]
            filter_parts.append(f"({' or '.join(tribunal_filters)})")
        
        if filters.get("uf"):
            uf_filters = [f"uf eq '{u}'" for u in filters["uf"]]
            filter_parts.append(f"({' or '.join(uf_filters)})")
        
        if filters.get("is_current") is not None:
            filter_parts.append(f"is_current eq {str(filters['is_current']).lower()}")
        
        if filters.get("year_min"):
            filter_parts.append(f"year ge {filters['year_min']}")
        
        if filters.get("effect"):
            effect_filters = [f"effect eq '{e}'" for e in filters["effect"]]
            filter_parts.append(f"({' or '.join(effect_filters)})")
        
        filter_str = " and ".join(filter_parts) if filter_parts else None
        
        # Executar busca
        search_params = {
            "search_text": query,
            "top": top_k,
            "select": ["chunk_id", "doc_type", "source", "tribunal", "uf", "region",
                       "effect", "title", "content", "citation", "year", "authority_score", "is_current"]
        }
        
        if filter_str:
            search_params["filter"] = filter_str
        
        if use_vector and query_vector:
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="embedding"
            )
            search_params["vector_queries"] = [vector_query]
        
        if use_semantic:
            search_params["query_type"] = "semantic"
            search_params["semantic_configuration_name"] = "kb-legal-semantic"
        
        results = search_client.search(**search_params)
        
        items = []
        for result in results:
            item = {
                "chunk_id": result.get("chunk_id"),
                "doc_type": result.get("doc_type"),
                "source": result.get("source"),
                "tribunal": result.get("tribunal"),
                "uf": result.get("uf"),
                "region": result.get("region"),
                "effect": result.get("effect"),
                "title": result.get("title"),
                "content": result.get("content"),
                "citation": result.get("citation"),
                "year": result.get("year"),
                "authority_score": result.get("authority_score"),
                "is_current": result.get("is_current"),
                "search_score": result.get("@search.score"),
                "reranker_score": result.get("@search.reranker_score")
            }
            items.append(item)
        
        response = {
            "status": "success",
            "query": query,
            "total": len(items),
            "results": items
        }
        
        if debug_mode:
            response["debug"] = {
                "filter": filter_str,
                "semantic": use_semantic,
                "vector": use_vector
            }
        
        return func.HttpResponse(
            json.dumps(response),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
