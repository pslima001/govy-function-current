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

def gen_embedding(text):
    return get_openai().embeddings.create(model="text-embedding-3-small", input=text[:30000]).data[0].embedding

def main(req: func.HttpRequest) -> func.HttpResponse:
    headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, x-functions-key", "Content-Type": "application/json"}
    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=200, headers=headers)
    try:
        body = req.get_json()
        chunks = body.get("chunks", [])
        gen_emb = body.get("generate_embeddings", True)
        if not chunks:
            return func.HttpResponse(json.dumps({"status": "error", "error": "chunks obrigatorio"}), status_code=400, headers=headers)
        docs, errors = [], []
        for i, c in enumerate(chunks):
            required = ["chunk_id", "doc_type", "source", "title", "content", "citation"]
            missing = [f for f in required if not c.get(f)]
            if missing:
                errors.append({"index": i, "error": f"Faltando: {missing}"})
                continue
            doc = {"chunk_id": c["chunk_id"], "doc_type": c["doc_type"], "source": c["source"], "tribunal": c.get("tribunal"), "uf": c.get("uf"), "title": c["title"], "content": c["content"], "citation": c["citation"], "year": c.get("year", 2025), "authority_score": c.get("authority_score", 0.5), "is_current": c.get("is_current", True)}
            if gen_emb:
                if c.get("embedding"):
                    doc["embedding"] = c["embedding"]
                else:
                    try:
                        doc["embedding"] = gen_embedding(f"{doc['title']} {doc['content']}")
                    except Exception as e:
                        errors.append({"index": i, "error": str(e)})
                        continue
            docs.append(doc)
        result = search_client.upsert_documents(docs) if docs else {"status": "error", "indexed": 0, "failed": 0, "errors": []}
        if errors:
            result["validation_errors"] = errors
        return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200 if result["status"]=="success" else 400, headers=headers)
    except Exception as e:
        return func.HttpResponse(json.dumps({"status": "error", "error": str(e)}), status_code=500, headers=headers)
