# govy/copilot/retrieval.py
"""
Retrieval — busca na KB jurídica e BI com filtros rígidos.

Regras:
- NUNCA retornar doutrina (doc_type != "doutrina")
- Usar apenas doc_types permitidos pela policy
- Reutilizar infraestrutura do kb_search.py existente
"""
import os
import logging
from typing import List, Optional

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from govy.copilot.contracts import Evidence
from govy.copilot.policy import Policy
from govy.api.kb_search import (
    generate_query_embedding,
    build_filter,
    run_search_with_mode_fallback,
)

logger = logging.getLogger(__name__)

AZURE_SEARCH_ENDPOINT = os.environ.get(
    "AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net"
)
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")


def _get_search_client() -> Optional[SearchClient]:
    if not AZURE_SEARCH_API_KEY:
        logger.warning("AZURE_SEARCH_API_KEY não configurada — retrieval desabilitado")
        return None
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )


# doc_types que NUNCA devem ser retornados, independente de configuração
_BLOCKED_DOC_TYPES = {"doutrina", "opinião", "opiniao", "artigo_externo"}

# Confidence mínima para aceitar evidência (evita ruído de baixo score)
MIN_CONFIDENCE = 0.15


def _is_blocked_doc_type(doc_type: str) -> bool:
    """Verifica se o doc_type é bloqueado (doutrina, opinião, etc.)."""
    if not doc_type:
        return False
    return doc_type.strip().lower() in _BLOCKED_DOC_TYPES


def _doc_to_evidence(doc: dict) -> Evidence:
    """Converte um resultado do Azure Search para Evidence."""
    content = doc.get("content") or doc.get("snippet") or ""
    if not content.strip():
        content = doc.get("text") or doc.get("summary") or ""
    snippet = content[:400] if len(content) > 400 else content

    score = doc.get("semantic_score") or doc.get("search_score") or 0.0
    confidence = min(score / 4.0, 1.0) if score else 0.0

    return Evidence(
        source="kb",
        id=doc.get("chunk_id") or doc.get("id") or "",
        snippet=snippet,
        confidence=confidence,
        title=doc.get("title") or doc.get("decisao_id"),
        doc_type=doc.get("doc_type"),
        tribunal=doc.get("tribunal"),
        uf=doc.get("uf"),
    )


def retrieve_from_kb(
    query: str,
    policy: Policy,
    uf: Optional[str] = None,
    tribunal: Optional[str] = None,
    procedural_stage: Optional[List[str]] = None,
    top_k: int = 6,
) -> List[Evidence]:
    """
    Busca na KB jurídica com filtros rígidos da policy.
    NUNCA retorna doutrina — filtro OData aplicado.
    """
    client = _get_search_client()
    if not client:
        return []

    query_vector = generate_query_embedding(query)

    # Construir filtros — um search por doc_type permitido
    # Estratégia: buscar todos os doc_types permitidos de uma vez
    all_results = []

    for doc_type in policy.allowed_doc_types:
        # Nunca incluir doutrina, mesmo se alguém alterar allowed_doc_types
        if doc_type == "doutrina":
            continue

        filter_str = build_filter(
            doc_type=doc_type,
            tribunal=tribunal,
            uf=uf,
            procedural_stage=procedural_stage,
            is_current=True,
        )

        results, _mode_info = run_search_with_mode_fallback(
            search_client=client,
            query=query,
            query_vector=query_vector,
            filter_str=filter_str,
            top_k=top_k,
            initial_use_vector=True,
            initial_use_semantic=True,
        )

        all_results.extend(results)

    # Ordenar por score e converter
    all_results.sort(
        key=lambda x: (x.get("semantic_score") or 0, x.get("search_score") or 0),
        reverse=True,
    )

    evidence = []
    seen_ids = set()
    for doc in all_results:
        if len(evidence) >= policy.max_evidence:
            break

        # Barreira final: rejeitar qualquer doc_type bloqueado que escapou
        doc_type = doc.get("doc_type") or ""
        if _is_blocked_doc_type(doc_type):
            logger.debug(f"retrieval: doc_type bloqueado '{doc_type}' filtrado")
            continue

        # Rejeitar doc sem conteúdo/snippet
        content = doc.get("content") or doc.get("snippet") or doc.get("text") or ""
        if not content.strip():
            logger.debug("retrieval: doc sem conteúdo filtrado")
            continue

        # Rejeitar low-confidence
        ev = _doc_to_evidence(doc)
        if ev.confidence < MIN_CONFIDENCE:
            logger.debug(f"retrieval: evidência com confidence={ev.confidence:.2f} < {MIN_CONFIDENCE} filtrada")
            continue

        # Deduplicar por id
        if ev.id and ev.id in seen_ids:
            continue
        seen_ids.add(ev.id)

        evidence.append(ev)

    return evidence


def retrieve_from_bi(query: str, policy: Policy) -> List[Evidence]:
    """
    Consulta BI (SQL/API) com whitelist de métricas e dimensões.
    TODO: Implementar quando camada BI estiver disponível.
    """
    # Placeholder — será plugado quando o módulo BI existir
    logger.info("retrieve_from_bi chamado — módulo BI ainda não implementado")
    return []


def retrieve_workspace_docs(
    query: str,
    workspace_id: str,
    policy: Policy,
    available_docs: Optional[List[dict]] = None,
) -> List[Evidence]:
    """
    Busca nos documentos do workspace (edital, TR, ETP, minuta, anexos).

    Fluxo:
    1. Verifica quais docs do workspace estão indexados
    2. Para docs indexados: busca no Azure Search filtrando por workspace
    3. Para docs não indexados: loga (handler já trata a mensagem)
    4. Retorna evidências encontradas com source="workspace_doc"

    Args:
        query: texto do usuário
        workspace_id: ID do workspace ou licitacao
        policy: policy vigente
        available_docs: lista de docs [{name, doc_type, indexed}] do contexto
    """
    available_docs = available_docs or []
    indexed_docs = [d for d in available_docs if d.get("indexed")]
    not_indexed_docs = [d for d in available_docs if not d.get("indexed")]

    if not_indexed_docs:
        names = [d.get("name", "?") for d in not_indexed_docs]
        logger.info(
            f"workspace_docs [{workspace_id}]: {len(not_indexed_docs)} docs "
            f"ainda não indexados: {names}"
        )

    if not indexed_docs:
        logger.info(f"workspace_docs [{workspace_id}]: nenhum doc indexado para buscar")
        return []

    # Buscar no Azure Search filtrando pelo workspace
    client = _get_search_client()
    if not client:
        return []

    query_vector = generate_query_embedding(query)

    # Buscar por cada doc_type presente no workspace
    indexed_doc_types = list({d.get("doc_type", "outro") for d in indexed_docs})
    all_results = []

    for doc_type in indexed_doc_types:
        if _is_blocked_doc_type(doc_type):
            continue

        # Filtro: doc_type + workspace_id (se campo existir no índice)
        filter_parts = [f"doc_type eq '{doc_type}'"]
        if workspace_id:
            filter_parts.append(
                f"(workspace_id eq '{workspace_id}' or "
                f"licitacao_id eq '{workspace_id}')"
            )
        filter_str = " and ".join(filter_parts)

        try:
            results, _mode_info = run_search_with_mode_fallback(
                search_client=client,
                query=query,
                query_vector=query_vector,
                filter_str=filter_str,
                top_k=4,
                initial_use_vector=True,
                initial_use_semantic=True,
            )
            all_results.extend(results)
        except Exception as e:
            # Se o filtro por workspace_id falhar (campo não existe),
            # faz fallback buscando só por doc_type
            logger.warning(
                f"workspace_docs: filtro workspace_id falhou ({e}), "
                f"tentando sem filtro de workspace"
            )
            fallback_filter = f"doc_type eq '{doc_type}'"
            try:
                results, _ = run_search_with_mode_fallback(
                    search_client=client,
                    query=query,
                    query_vector=query_vector,
                    filter_str=fallback_filter,
                    top_k=4,
                    initial_use_vector=True,
                    initial_use_semantic=True,
                )
                all_results.extend(results)
            except Exception as e2:
                logger.error(f"workspace_docs: fallback também falhou: {e2}")

    # Converter e filtrar
    all_results.sort(
        key=lambda x: (x.get("semantic_score") or 0, x.get("search_score") or 0),
        reverse=True,
    )

    evidence = []
    seen_ids = set()
    for doc in all_results:
        if len(evidence) >= policy.max_evidence:
            break

        content = doc.get("content") or doc.get("snippet") or doc.get("text") or ""
        if not content.strip():
            continue

        ev = _doc_to_evidence(doc)
        ev.source = "workspace_doc"

        if ev.confidence < MIN_CONFIDENCE:
            continue
        if ev.id and ev.id in seen_ids:
            continue
        seen_ids.add(ev.id)

        evidence.append(ev)

    doc_names = [d.get("name", "?") for d in indexed_docs]
    logger.info(
        f"workspace_docs [{workspace_id}]: buscou em {doc_names}, "
        f"encontrou {len(evidence)} evidências"
    )
    return evidence
