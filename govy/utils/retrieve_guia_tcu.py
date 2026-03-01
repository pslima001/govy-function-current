"""
GOVY - Retriever dedicado para guia_tcu (filtros fixos de governanca)
======================================================================
Funcao utilitaria que busca chunks do Manual TCU no kb-legal com
filtros de governanca forcados.

Regras fixas (nao-negociaveis):
  - doc_type eq 'guia_tcu'
  - is_citable eq false
  - (opcional) filtro por procedural_stage
  - topK controlado + threshold de score

Uso:
  from govy.utils.retrieve_guia_tcu import retrieve_guia_tcu
  results = retrieve_guia_tcu("prazo para impugnacao do edital", stage_tag="edital", top_k=10)
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

_FORCED_DOC_TYPE = "guia_tcu"
_FORCED_IS_CITABLE = False

VALID_STAGES = frozenset({
    "PLANEJAMENTO", "EDITAL", "SELECAO", "CONTRATO", "GESTAO", "GOVERNANCA",
})

_STAGE_TAG_TO_INDEX = {
    "planejamento": "PLANEJAMENTO",
    "edital": "EDITAL",
    "selecao": "SELECAO",
    "sele\u00e7\u00e3o": "SELECAO",
    "contrato": "CONTRATO",
    "gestao": "GESTAO",
    "gest\u00e3o": "GESTAO",
    "governanca": "GOVERNANCA",
    "governan\u00e7a": "GOVERNANCA",
}

DEFAULT_TOP_K = 10
MAX_TOP_K = 30


@dataclass
class GuiaTcuResult:
    chunk_id: str
    section_id: str
    section_title: str
    stage_tag: str
    source_url: str
    text_snippet: str
    score: float
    procedural_stage: str
    citation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "stage_tag": self.stage_tag,
            "source_url": self.source_url,
            "text_snippet": self.text_snippet,
            "score": self.score,
            "procedural_stage": self.procedural_stage,
            "citation": self.citation,
        }


def _get_search_client():
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    if not AZURE_SEARCH_API_KEY:
        raise RuntimeError("AZURE_SEARCH_API_KEY not configured")
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )


def _generate_embedding(text: str) -> Optional[List[float]]:
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None


def _build_filter(stage_tag: Optional[str] = None) -> str:
    filters = [
        f"doc_type eq '{_FORCED_DOC_TYPE}'",
        f"is_citable eq {str(_FORCED_IS_CITABLE).lower()}",
    ]
    if stage_tag:
        normalized = _STAGE_TAG_TO_INDEX.get(stage_tag.lower().strip())
        if normalized and normalized in VALID_STAGES:
            filters.append(f"procedural_stage eq '{normalized}'")
        else:
            logger.warning(f"Invalid stage_tag '{stage_tag}' ignored. Valid: {sorted(VALID_STAGES)}")
    return " and ".join(filters)


def _extract_section_id(claim_pattern: str) -> str:
    if "section=" in claim_pattern:
        return claim_pattern.split("section=")[-1].split(";")[0]
    return ""


def _extract_stage_tag(claim_pattern: str) -> str:
    if "stage_tag=" in claim_pattern:
        return claim_pattern.split("stage_tag=")[1].split(";")[0]
    return ""


def retrieve_guia_tcu(
    query: str,
    stage_tag: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = 0.0,
    use_vector: bool = True,
    use_semantic: bool = True,
    snippet_length: int = 300,
) -> List[GuiaTcuResult]:
    """Retrieve chunks from the TCU Manual KB with governance filters."""
    top_k = max(1, min(top_k, MAX_TOP_K))
    filter_str = _build_filter(stage_tag)
    search_client = _get_search_client()

    search_params: Dict[str, Any] = {
        "search_text": query,
        "filter": filter_str,
        "top": top_k,
        "select": [
            "chunk_id", "title", "content", "citation",
            "source", "claim_pattern", "procedural_stage",
        ],
    }

    if use_vector:
        embedding = _generate_embedding(query)
        if embedding:
            from azure.search.documents.models import VectorizedQuery
            search_params["vector_queries"] = [
                VectorizedQuery(vector=embedding, k_nearest_neighbors=top_k, fields="embedding")
            ]

    if use_semantic:
        search_params["query_type"] = "semantic"
        search_params["semantic_configuration_name"] = "semantic-config"

    try:
        results = search_client.search(**search_params)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        if use_semantic or use_vector:
            search_params.pop("vector_queries", None)
            search_params.pop("query_type", None)
            search_params.pop("semantic_configuration_name", None)
            try:
                results = search_client.search(**search_params)
            except Exception as e2:
                logger.error(f"Text-only fallback also failed: {e2}")
                return []
        else:
            return []

    output: List[GuiaTcuResult] = []
    for r in results:
        score = r.get("@search.reranker_score") or r.get("@search.score") or 0.0
        if score_threshold > 0 and score < score_threshold:
            continue
        content = r.get("content", "")
        claim_pattern = r.get("claim_pattern", "")
        result = GuiaTcuResult(
            chunk_id=r.get("chunk_id", ""),
            section_id=_extract_section_id(claim_pattern),
            section_title=r.get("title", ""),
            stage_tag=_extract_stage_tag(claim_pattern),
            source_url=r.get("source", ""),
            text_snippet=content[:snippet_length] if content else "",
            score=round(float(score), 4),
            procedural_stage=r.get("procedural_stage", ""),
            citation=r.get("citation", ""),
        )
        output.append(result)
    return output


def retrieve_guia_tcu_dicts(
    query: str,
    stage_tag: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Same as retrieve_guia_tcu but returns dicts."""
    return [r.to_dict() for r in retrieve_guia_tcu(query, stage_tag, top_k, **kwargs)]
