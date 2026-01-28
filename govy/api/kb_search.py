import json, logging, os, sys
import azure.functions as func
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'govy', 'api'))
from openai import OpenAI
from govy.api import search_client

logger = logging.getLogger(__name__)
_openai = None

def get_openai():
    global _openai
    if not _openai:
        _openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai

def gen_query_embedding(query):
    return get_openai().embeddings.create(model="text-embedding-3-small", input=query[:8000]).data[0].embedding

def main(req: func.HttpRequest) -> func.HttpResponse:
    headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, x-functions-key", "Content-Type": "application/json"}
    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=200, headers=headers)
    try:
        body = req.get_json()
        query = body.get("query", "").strip()
        top_k = max(1, min(body.get("top_k", 10), 50))
        filters = body.get("filters", {})
        use_semantic = body.get("use_semantic", True)
        use_vector = body.get("use_vector", True)
        debug = body.get("debug", False)
        if not query:
            return func.HttpResponse(json.dumps({"status": "error", "error": "query obrigatorio"}), status_code=400, headers=headers)
        embedding = None
        if use_vector:
            try:
                embedding = gen_query_embedding(query)
            except:
                pass
        result = search_client.hybrid_search(query=query, embedding=embedding, top_k=top_k, filters=filters, use_semantic=use_semantic, debug=debug)
        return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200 if result["status"]=="success" else 500, headers=headers)
    except Exception as e:
        return func.HttpResponse(json.dumps({"status": "error", "error": str(e)}), status_code=500, headers=headers)
