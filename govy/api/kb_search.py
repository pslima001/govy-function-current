"""
GOVY - Handler do Endpoint /api/kb/search
SPEC 1.2 - Knowledge Base Juridica

Busca hibrida com fallback juridico:
- scenario (1-4) deriva desired_effect automaticamente
- Fallback jurisdicao: TCE da UF -> TCU -> TCE da regiao -> TCE Brasil
- Fallback effect: desired_effect -> CONDICIONAL -> NUNCA oposto
- Filtros por secao e procedural_stage
- Preferencia: vital > fundamento_legal > tese

FALLBACK AUTOMATICO DE MODO (v3.1 - 30/01/2026):
- Se busca retorna 0, tenta automaticamente outros modos
- Ordem: vector+semantic -> semantic-only -> text-only
- Maximo 3 tentativas por request
- TCU: ignora uf/region no filtro (REGRA #3)
- top_k limitado a 50
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

# =================================================================================
# CONFIGURACAO
# =================================================================================

AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Limites operacionais
MAX_TOP_K = 50
MIN_TOP_K = 1

# =================================================================================
# CONSTANTES SPEC 1.2
# =================================================================================

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

# Ordem de fallback de modo de busca
FALLBACK_MODES = [
    {"use_vector": True, "use_semantic": True},    # Tentativa 0: hibrido completo
    {"use_vector": False, "use_semantic": True},   # Tentativa 1: semantic-only
    {"use_vector": False, "use_semantic": False},  # Tentativa 2: text-only
]


def generate_query_embedding(text: str) -> Optional[List[float]]:
    """
    Gera embedding para a query.
    Retorna None se OPENAI_API_KEY nao estiver configurada.
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY nao configurada - vector search desabilitado")
        return None
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erro ao gerar embedding: {e}")
        return None


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
    """
    Constroi filter string para Azure Search.
    
    REGRA CRITICA #3: Se tribunal=="TCU", IGNORA uf e region.
    Azure Search: uf eq null NAO encontra uf="" (string vazia).
    """
    filters = []

    if doc_type:
        filters.append(f"doc_type eq '{doc_type}'")
    
    if tribunal:
        filters.append(f"tribunal eq '{tribunal}'")
        # REGRA #3: TCU nao filtra por uf nem region
        if tribunal.upper() == "TCU":
            uf = None
            region = None
    
    if uf:
        filters.append(f"uf eq '{uf}'")
    
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


def execute_search_attempt(
    search_client: SearchClient,
    query: str,
    query_vector: Optional[List[float]],
    filter_str: Optional[str],
    top_k: int,
    use_semantic: bool,
    use_vector: bool
) -> Tuple[List[Dict], int, Optional[str]]:
    """
    Executa uma tentativa de busca e retorna (results, total, error).
    Nao lanca excecao - captura e retorna como error string.
    """
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
        search_params["semantic_configuration_name"] = "semantic-config"

    try:
        results = search_client.search(**search_params)

        docs = []
        total_count = 0
        
        # Tentar obter total real do Azure Search
        try:
            total_count = results.get_count() or 0
        except:
            pass
        
        for result in results:
            doc = dict(result)
            doc["search_score"] = result.get("@search.score", 0)
            doc["semantic_score"] = result.get("@search.reranker_score", 0)
            doc.pop("embedding", None)
            docs.append(doc)

        # Se nao conseguiu total real, usar len(docs)
        if total_count == 0:
            total_count = len(docs)

        return docs, total_count, None
    except Exception as e:
        logger.error(f"Erro na busca (vector={use_vector}, semantic={use_semantic}): {e}")
        return [], 0, str(e)


def run_search_with_mode_fallback(
    search_client: SearchClient,
    query: str,
    query_vector: Optional[List[float]],
    filter_str: Optional[str],
    top_k: int,
    initial_use_vector: bool,
    initial_use_semantic: bool
) -> Tuple[List[Dict], Dict]:
    """
    Executa busca com fallback automatico de modo.
    Retorna (results, mode_fallback_info).
    """
    mode_fallback_info = {
        "attempts": [],
        "final_mode": None
    }

    # Determinar ponto de partida no fallback baseado nos flags iniciais
    if initial_use_vector and initial_use_semantic:
        start_index = 0  # Comecar do hibrido completo
    elif not initial_use_vector and initial_use_semantic:
        start_index = 1  # Comecar do semantic-only
    else:
        start_index = 2  # Comecar do text-only (sem fallback possivel)

    # Se nao temos query_vector, pular tentativa com vector
    if query_vector is None and start_index == 0:
        # Registrar que vector foi pulado por falta de embedding
        mode_fallback_info["attempts"].append({
            "use_vector": True,
            "use_semantic": True,
            "total": 0,
            "error": "query_vector indisponivel (sem OPENAI_API_KEY ou erro)"
        })
        start_index = 1  # Pular para semantic-only

    # Executar tentativas em ordem
    for i in range(start_index, len(FALLBACK_MODES)):
        mode = FALLBACK_MODES[i]
        use_vector = mode["use_vector"]
        use_semantic = mode["use_semantic"]

        results, total, error = execute_search_attempt(
            search_client=search_client,
            query=query,
            query_vector=query_vector if use_vector else None,
            filter_str=filter_str,
            top_k=top_k,
            use_semantic=use_semantic,
            use_vector=use_vector
        )

        attempt_info = {
            "use_vector": use_vector,
            "use_semantic": use_semantic,
            "total": total,
            "error": error
        }
        mode_fallback_info["attempts"].append(attempt_info)

        if total > 0:
            mode_fallback_info["final_mode"] = {
                "use_vector": use_vector,
                "use_semantic": use_semantic
            }
            return results, mode_fallback_info

    # Nenhuma tentativa retornou resultados
    mode_fallback_info["final_mode"] = None
    return [], mode_fallback_info


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
        "mode": "jurisdiction_fallback",
        "mode_fallback_info": None
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

            # Usar fallback de modo para cada tentativa de jurisdicao
            results, mode_fb_info = run_search_with_mode_fallback(
                search_client=search_client,
                query=query,
                query_vector=query_vector,
                filter_str=filter_str,
                top_k=top_k,
                initial_use_vector=use_vector,
                initial_use_semantic=use_semantic
            )

            attempt_info = {
                "jurisdiction": step["name"],
                "effect": current_effect,
                "filter": filter_str,
                "results_count": len(results),
                "mode_attempts": mode_fb_info["attempts"]
            }
            debug_info["attempts"].append(attempt_info)

            if results:
                debug_info["found_at"] = step["name"]
                debug_info["found_effect"] = current_effect
                debug_info["mode_fallback_info"] = mode_fb_info
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

    # Usar fallback de modo
    results, mode_fb_info = run_search_with_mode_fallback(
        search_client=search_client,
        query=query,
        query_vector=query_vector,
        filter_str=filter_str,
        top_k=top_k,
        initial_use_vector=use_vector,
        initial_use_semantic=use_semantic
    )

    debug_info = {
        "mode": "simple",
        "filter": filter_str,
        "mode_fallback_info": mode_fb_info
    }

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
        user_uf = body.get("user_uf") or body.get("uf")  # Aceitar ambos
        
        # Cap de top_k para seguranca operacional
        top_k = body.get("top_k", 10)
        top_k = max(MIN_TOP_K, min(top_k, MAX_TOP_K))
        
        filters = body.get("filters", {})
        
        # Aceitar tribunal no body diretamente (alem de filters.tribunal)
        if body.get("tribunal") and not filters.get("tribunal"):
            filters["tribunal"] = body.get("tribunal")
        
        use_semantic = body.get("use_semantic", True)
        use_vector = body.get("use_vector", True)
        debug = body.get("debug", False)

        if user_uf and user_uf not in UF_TO_REGION:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": f"UF invalida: {user_uf}"}),
                status_code=400,
                headers=cors_headers
            )

        # Gerar embedding uma unica vez (reusar em todas tentativas)
        # Se OPENAI_API_KEY nao configurada, retorna None e fallback trata
        query_vector = None
        if use_vector:
            query_vector = generate_query_embedding(query)
            # Se falhou, o fallback vai pular para semantic-only

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

        # Extrair mode_fallback_info para resposta
        mode_fb = debug_info.get("mode_fallback_info", {})

        response = {
            "status": "success",
            "query": query,
            "total": len(results),
            "results": results,
            "fallback_info": {
                "scenario": scenario,
                "desired_effect": debug_info.get("desired_effect"),
                "found_at": debug_info.get("found_at"),
                "found_effect": debug_info.get("found_effect"),
                "mode_attempts": mode_fb.get("attempts", []),
                "final_mode": mode_fb.get("final_mode")
            }
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
