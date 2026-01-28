# govy/api/juris_buscar.py
import azure.functions as func
import json
import logging
import os
import psycopg2
import openai

PG_HOST = "postgresqlgovy-kb.postgres.database.azure.com"
PG_DB = "govy_kb"
PG_USER = "pgadmin"

def get_db_connection():
    return psycopg2.connect(host=PG_HOST, database=PG_DB, user=PG_USER, password=os.environ.get("PG_PASSWORD"), sslmode="require")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("juris_buscar chamado")
    try:
        body = req.get_json()
        query = body.get("query", "")
        limit = body.get("limit", 5)
        
        if not query:
            return func.HttpResponse(json.dumps({"error": "Campo 'query' obrigatorio"}), status_code=400, mimetype="application/json")
        
        openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        emb_response = openai_client.embeddings.create(model="text-embedding-3-small", input=query)
        query_embedding = emb_response.data[0].embedding
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, acordao, relator, data, colegiado, tema_principal,
                   ementa, entendimento, citacao_direta, quando_usar, link,
                   1 - (embedding <=> %s::vector) as similaridade
            FROM kb_jurisprudencia
            WHERE embedding IS NOT NULL AND status = 'aprovado'
            ORDER BY embedding <=> %s::vector LIMIT %s
        """, (query_embedding, query_embedding, limit))
        
        rows = cur.fetchall()
        resultados = []
        for row in rows:
            resultados.append({
                "id": row[0], "acordao": row[1], "relator": row[2], "data": row[3],
                "colegiado": row[4], "tema_principal": row[5], "ementa": row[6],
                "entendimento": row[7] or [], "citacao_direta": row[8],
                "quando_usar": row[9] or [], "link": row[10],
                "similaridade": round(row[11], 4) if row[11] else 0
            })
        
        cur.close()
        conn.close()
        
        return func.HttpResponse(json.dumps({"status": "success", "query": query, "total": len(resultados), "resultados": resultados}, ensure_ascii=False), mimetype="application/json")
    except Exception as e:
        logging.error(f"Erro: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")