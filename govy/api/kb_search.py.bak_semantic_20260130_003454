"""
GOVY - Handler do Endpoint /api/kb/search
SPEC 1.2 - Knowledge Base Juridica

Busca hibrida com fallback juridico:
- scenario (1-4) deriva desired_effect automaticamente
- Fallback jurisdicao: TCE da UF -> TCU -> TCE da regiao -> TCE Brasil
- Fallback effect: desired_effect -> CONDICIONAL -> NUNCA oposto
- Filtros por secao e procedural_stage
- Preferencia: vital > fundamento_legal > tese
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import azure.functions as func
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import OpenAI

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURACAO
# =============================================================================

AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# =============================================================================
# CONSTANTES SPEC 1.2
# =============================================================================

SCENARIO_TO_EFFECT = {
    1: "FLEXIBILIZA",
    2: "RIGORIZA",
    3: "FLEXIBILIZA",
    4: "RIGORIZA",
}

UF_TO_REGION = {
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    "DF": "CENTRO_OESTE", "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE",
    "AC": "NORTE", "AM": "NORTE", "AP": "NORTE", "PA": "NORTE",
    "RO": "NORTE", "RR": "NORTE", "TO": "NORTE",
}

SECAO_PRIORITY = ["vital", "fundamento_legal", "tese", "limites", "contexto_minimo"]


def generate_query_embedding(text: str) -> List[float]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def build_filter(
    doc_type: Optional[str] = None,
    tribunal: Optional[str] = None,
    uf: Optional[str] = None,
    region: Optional[str] = None,
    effect: Optional[str] = None,
    secao: Optional[List[str]] = None,
    procedural_stage: Optional[List[str]] = None,
    is_current: Optional[bool] = None,
    year_min: Optional[int] = None
) -> Optional[str]:
    filters = []
    
    if doc_type:
        filters.append(f"doc_type eq '{doc_type}'")
    if tribunal:
        filters.append(f"tribunal eq '{tribunal}'")
    if uf:
        filters.append(f"uf eq '{uf}'")
    # NAO adicionar uf eq null para TCU - chunks podem ter uf vazio ou null
    if region:
        filters.append(f"region eq '{region}'")
    if effect:
        filters.append(f"effect eq '{effect}'")
    if secao:
        secao_filters = [f"secao eq '{s}'" for s in secao]
        filters.append(f"({' or '.join(secao_filters)})")
    if procedural_stage:
        stage_filters = [f"procedural_stage eq '{s}'" for s in procedural_stage]
        filters.append(f"({' or '.join(stage_filters)})")
    if is_current is not None:
        filters.append(f"is_current eq {str(is_current).lower()}")
    if year_min:
        filters.append(f"year ge {year_min}")
    
    return " and ".join(filters) if filters else None


def execute_search(
    search_client: SearchClient,
    query: str,
    query_vector: Optional[List[float]],
    filter_str: Optional[str],
    top_k: int = 10,
    use_semantic: bool = True,
    use_vector: bool = True
) -> List[Dict]:
    
    search_params = {
        "search_text": query,
        "top": top_k,
        "include_total_count": True
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
        search_params["semantic_configuration_name"] = "default"
    
    try:
        results = search_client.search(**search_params)
        
        docs = []
        for result in results:
            doc = dict(result)
            doc["search_score"] = result.get("@search.score", 0)
            doc["semantic_score"] = result.get("@search.reranker_score", 0)
            doc.pop("embedding", None)
            docs.append(doc)
        
        return docs
    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        return []


def search_with_jurisdiction_fallback(
    search_client: SearchClient,
    query: str,
    query_vector: Optional[List[float]],
    user_uf: Optional[str],
    desired_effect: str,
    secao: Optional[List[str]] = None,
    procedural_stage: Optional[List[str]] = None,
    top_k: int = 10,
    use_semantic: bool = True,
    use_vector: bool = True
) -> Tuple[List[Dict], Dict]:
    
    debug_info = {
        "user_uf": user_uf,
        "user_region": UF_TO_REGION.get(user_uf) if user_uf else None,
        "desired_effect": desired_effect,
        "attempts": [],
        "mode": "jurisdiction_fallback"
    }
    
    user_region = UF_TO_REGION.get(user_uf) if user_uf else None
    
    effects_to_try = [desired_effect]
    if desired_effect != "CONDICIONAL":
        effects_to_try.append("CONDICIONAL")
    
    jurisdiction_steps = []
    if user_uf:
        jurisdiction_steps.append({"name": f"TCE_{user_uf}", "tribunal": "TCE", "uf": user_uf, "region": None})
    jurisdiction_steps.append({"name": "TCU", "tribunal": "TCU", "uf": None, "region": None})
    if user_region:
        jurisdiction_steps.append({"name": f"TCE_REGION_{user_region}", "tribunal": "TCE", "uf": None, "region": user_region})
    jurisdiction_steps.append({"name": "TCE_BRASIL", "tribunal": "TCE", "uf": None, "region": None})
    
    for current_effect in effects_to_try:
        for step in jurisdiction_steps:
            filter_str = build_filter(
                doc_type="jurisprudencia",
                tribunal=step["tribunal"],
                uf=step["uf"],
                region=step["region"],
                effect=current_effect,
                secao=secao,
                procedural_stage=procedural_stage,
                is_current=True
            )
            
            attempt_info = {
                "jurisdiction": step["name"],
                "effect": current_effect,
                "filter": filter_str,
                "results_count": 0
            }
            
            results = execute_search(
                search_client=search_client,
                query=query,
                query_vector=query_vector,
                filter_str=filter_str,
                top_k=top_k,
                use_semantic=use_semantic,
                use_vector=use_vector
            )
            
            attempt_info["results_count"] = len(results)
            debug_info["attempts"].append(attempt_info)
            
            if results:
                debug_info["found_at"] = step["name"]
                debug_info["found_effect"] = current_effect
                results.sort(key=lambda x: (
                    SECAO_PRIORITY.index(x.get("secao")) if x.get("secao") in SECAO_PRIORITY else 99,
                    -x.get("search_score", 0)
                ))
                return results[:top_k], debug_info
    
    debug_info["found_at"] = None
    debug_info["found_effect"] = None
    return [], debug_info


def search_simple(
    search_client: SearchClient,
    query: str,
    query_vector: Optional[List[float]],
    filters: Dict,
    top_k: int = 10,
    use_semantic: bool = True,
    use_vector: bool = True
) -> Tuple[List[Dict], Dict]:
    
    filter_str = build_filter(
        doc_type=filters.get("doc_type"),
        tribunal=filters.get("tribunal"),
        uf=filters.get("uf"),
        effect=filters.get("effect"),
        secao=filters.get("secao"),
        procedural_stage=filters.get("procedural_stage"),
        is_current=filters.get("is_current"),
        year_min=filters.get("year_min")
    )
    
    debug_info = {"mode": "simple", "filter": filter_str}
    
    results = execute_search(
        search_client=search_client,
        query=query,
        query_vector=query_vector,
        filter_str=filter_str,
        top_k=top_k,
        use_semantic=use_semantic,
        use_vector=use_vector
    )
    
    return results, debug_info


def main(req: func.HttpRequest) -> func.HttpResponse:
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
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "Invalid JSON"}),
                status_code=400,
                headers=cors_headers
            )
        
        query = body.get("query", "")
        if not query:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "query e obrigatorio"}),
                status_code=400,
                headers=cors_headers
            )
        
        scenario = body.get("scenario")
        user_uf = body.get("user_uf")
        top_k = body.get("top_k", 10)
        filters = body.get("filters", {})
        use_semantic = body.get("use_semantic", True)
        use_vector = body.get("use_vector", True)
        debug = body.get("debug", False)
        
        if user_uf and user_uf not in UF_TO_REGION:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": f"UF invalida: {user_uf}"}),
                status_code=400,
                headers=cors_headers
            )
        
        query_vector = None
        if use_vector:
            try:
                query_vector = generate_query_embedding(query)
            except Exception as e:
                logger.warning(f"Erro ao gerar embedding: {e}")
                use_vector = False
        
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
        )
        
        if scenario and scenario in SCENARIO_TO_EFFECT:
            desired_effect = SCENARIO_TO_EFFECT[scenario]
            results, debug_info = search_with_jurisdiction_fallback(
                search_client=search_client,
                query=query,
                query_vector=query_vector,
                user_uf=user_uf,
                desired_effect=desired_effect,
                secao=filters.get("secao"),
                procedural_stage=filters.get("procedural_stage"),
                top_k=top_k,
                use_semantic=use_semantic,
                use_vector=use_vector
            )
            debug_info["scenario"] = scenario
        else:
            results, debug_info = search_simple(
                search_client=search_client,
                query=query,
                query_vector=query_vector,
                filters=filters,
                top_k=top_k,
                use_semantic=use_semantic,
                use_vector=use_vector
            )
        
        response = {
            "status": "success",
            "query": query,
            "total": len(results),
            "results": results,
            "fallback_info": {
                "scenario": scenario,
                "desired_effect": debug_info.get("desired_effect"),
                "found_at": debug_info.get("found_at"),
                "found_effect": debug_info.get("found_effect")
            } if scenario else None
        }
        
        if debug:
            response["debug"] = debug_info
        
        return func.HttpResponse(
            json.dumps(response, ensure_ascii=False, default=str),
            status_code=200,
            headers=cors_headers
        )
        
    except Exception as e:
        logger.exception(f"Erro no search: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "error": str(e)}),
            status_code=500,
            headers=cors_headers
        )
