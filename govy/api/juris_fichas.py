# govy/api/juris_fichas.py
import azure.functions as func
import json
import logging
import os
import psycopg2

PG_HOST = "postgresqlgovy-kb.postgres.database.azure.com"
PG_DB = "govy_kb"
PG_USER = "pgadmin"

def get_db_connection():
    return psycopg2.connect(host=PG_HOST, database=PG_DB, user=PG_USER, password=os.environ.get("PG_PASSWORD"), sslmode="require")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("juris_fichas chamado")
    try:
        status = req.params.get("status")
        tema = req.params.get("tema")
        limit = int(req.params.get("limit", 50))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = "SELECT id, acordao, relator, data, colegiado, tema_principal, temas_secundarios, palavras_chave, ementa, entendimento, quando_usar, quando_nao_usar, status, link, criado_em FROM kb_jurisprudencia WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        if tema:
            query += " AND tema_principal = %s"
            params.append(tema)
        
        query += " ORDER BY criado_em DESC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        fichas = []
        for row in rows:
            fichas.append({
                "id": row[0], "acordao": row[1], "relator": row[2], "data": row[3],
                "colegiado": row[4], "tema_principal": row[5], "temas_secundarios": row[6] or [],
                "palavras_chave": row[7] or [], "ementa": row[8], "entendimento": row[9] or [],
                "quando_usar": row[10] or [], "quando_nao_usar": row[11] or [],
                "status": row[12], "link": row[13],
                "criado_em": row[14].isoformat() if row[14] else None
            })
        
        cur.execute("SELECT status, COUNT(*) FROM kb_jurisprudencia GROUP BY status")
        stats = dict(cur.fetchall())
        
        cur.close()
        conn.close()
        
        return func.HttpResponse(json.dumps({
            "status": "success", "total": len(fichas),
            "stats": {"pendente": stats.get("pendente", 0), "aprovado": stats.get("aprovado", 0), "rejeitado": stats.get("rejeitado", 0)},
            "fichas": fichas
        }, ensure_ascii=False), mimetype="application/json")
    except Exception as e:
        logging.error(f"Erro: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")