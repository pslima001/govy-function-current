# govy/api/juris_validar.py
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
    logging.info("juris_validar chamado")
    try:
        body = req.get_json()
        ficha_id = body.get("id")
        if not ficha_id:
            return func.HttpResponse(json.dumps({"error": "Campo 'id' obrigatorio"}), status_code=400, mimetype="application/json")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE kb_jurisprudencia SET
                tema_principal = COALESCE(%s, tema_principal),
                palavras_chave = COALESCE(%s, palavras_chave),
                ementa = COALESCE(%s, ementa),
                entendimento = COALESCE(%s, entendimento),
                quando_usar = COALESCE(%s, quando_usar),
                quando_nao_usar = COALESCE(%s, quando_nao_usar),
                status = %s, validado_por = %s, validado_em = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, acordao, status, validado_por, validado_em
        """, (
            body.get("tema_principal"),
            body.get("palavras_chave") or None,
            body.get("ementa"),
            body.get("entendimento") or None,
            body.get("quando_usar") or None,
            body.get("quando_nao_usar") or None,
            body.get("status", "aprovado"),
            body.get("usuario", "juridico"),
            ficha_id
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if result:
            return func.HttpResponse(json.dumps({"status": "success", "ficha": {"id": result[0], "acordao": result[1], "status": result[2], "validado_por": result[3], "validado_em": result[4].isoformat() if result[4] else None}}, ensure_ascii=False), mimetype="application/json")
        return func.HttpResponse(json.dumps({"error": "Ficha nao encontrada"}), status_code=404, mimetype="application/json")
    except Exception as e:
        logging.error(f"Erro: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")