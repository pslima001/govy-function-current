import os
import logging
from typing import List, Dict, Optional, Any
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

logger = logging.getLogger(__name__)
_search_client = None

def get_search_client():
    global _search_client
    if _search_client is not None:
        return _search_client
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
    if not endpoint or not api_key:
        raise ValueError("AZURE_SEARCH_ENDPOINT e AZURE_SEARCH_API_KEY obrigatorios")
    _search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(api_key))
    return _search_client

def upsert_documents(documents):
    client = get_search_client()
    result = {"status": "success", "indexed": 0, "failed": 0, "errors": []}
    if not documents:
        return result
    try:
        response = client.upload_documents(documents=documents)
        for item in response:
            if item.succeeded:
                result["indexed"] += 1
            else:
                result["failed"] += 1
                result["errors"].append({"key": item.key, "error": item.error_message})
        if result["failed"] > 0:
            result["status"] = "partial" if result["indexed"] > 0 else "error"
    except Exception as e:
        result["status"] = "error"
        result["errors"].append({"error": str(e)})
    return result

def hybrid_search(query, embedding=None, top_k=10, filters=None, use_semantic=True, debug=False):
    client = get_search_client()
    result = {"status": "success", "query": query, "total": 0, "results": []}
    try:
        filter_clauses = []
        if filters:
            if filters.get("doc_type"):
                types = [filters["doc_type"]] if isinstance(filters["doc_type"], str) else filters["doc_type"]
                filter_clauses.append("(" + " or ".join([f"doc_type eq '{t}'" for t in types]) + ")")
            if filters.get("source"):
                sources = [filters["source"]] if isinstance(filters["source"], str) else filters["source"]
                filter_clauses.append("(" + " or ".join([f"source eq '{s}'" for s in sources]) + ")")
            if filters.get("tribunal"):
                tribunais = [filters["tribunal"]] if isinstance(filters["tribunal"], str) else filters["tribunal"]
                filter_clauses.append("(" + " or ".join([f"tribunal eq '{t}'" for t in tribunais]) + ")")
            if filters.get("uf"):
                ufs = [filters["uf"]] if isinstance(filters["uf"], str) else filters["uf"]
                filter_clauses.append("(" + " or ".join([f"uf eq '{u}'" for u in ufs]) + ")")
            if "is_current" in filters:
                filter_clauses.append(f"is_current eq {str(filters['is_current']).lower()}")
            if filters.get("year_min"):
                filter_clauses.append(f"year ge {filters['year_min']}")
            if filters.get("year_max"):
                filter_clauses.append(f"year le {filters['year_max']}")
        filter_expr = " and ".join(filter_clauses) if filter_clauses else None
        vector_queries = None
        if embedding:
            vector_queries = [VectorizedQuery(vector=embedding, k_nearest_neighbors=top_k, fields="embedding")]
        search_kwargs = {
            "search_text": query,
            "top": top_k,
            "filter": filter_expr,
            "select": ["chunk_id", "doc_type", "source", "tribunal", "uf", "title", "content", "citation", "year", "authority_score", "is_current"],
            "scoring_profile": "authority-boost"
        }
        if vector_queries:
            search_kwargs["vector_queries"] = vector_queries
        if use_semantic:
            search_kwargs["query_type"] = "semantic"
            search_kwargs["semantic_configuration_name"] = "semantic-config"
        response = client.search(**search_kwargs)
        for doc in response:
            item = {
                "chunk_id": doc.get("chunk_id"), "doc_type": doc.get("doc_type"), "source": doc.get("source"),
                "tribunal": doc.get("tribunal"), "uf": doc.get("uf"), "title": doc.get("title"),
                "content": doc.get("content"), "citation": doc.get("citation"), "year": doc.get("year"),
                "authority_score": doc.get("authority_score"), "is_current": doc.get("is_current"),
                "search_score": doc.get("@search.score")
            }
            if "@search.reranker_score" in doc:
                item["semantic_score"] = doc.get("@search.reranker_score")
            result["results"].append(item)
        result["total"] = len(result["results"])
        if debug:
            result["debug"] = {"filter": filter_expr, "semantic": use_semantic, "vector": embedding is not None}
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result
