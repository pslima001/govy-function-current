# govy/api/consult_llms.py
"""
Handler para consulta a múltiplos LLMs.
Recebe candidatos e retorna a escolha de cada LLM.
"""
import json
import logging
import azure.functions as func

logger = logging.getLogger(__name__)


def handle_consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    """
    Consulta 5 LLMs para escolher o melhor candidato.
    
    Espera JSON:
    {
        "parametro": "e001",
        "candidatos": [
            {"value": "5 dias", "score": 12, "context": "..."},
            {"value": "30 dias", "score": 10, "context": "..."}
        ]
    }
    """
    try:
        body = req.get_json()
        parametro = body.get("parametro")
        candidatos = body.get("candidatos", [])
        
        if not parametro or not candidatos:
            return func.HttpResponse(
                json.dumps({"error": "Envie parametro e candidatos"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Normaliza candidatos (valor -> value)
        candidatos_norm = []
        for c in candidatos:
            candidatos_norm.append({
                "value": c.get("valor") or c.get("value") or "",
                "score": c.get("score", 0),
                "context": c.get("context") or c.get("evidence") or ""
            })
        
        from govy.utils.multi_llm import consultar_llms, obter_api_keys
        
        api_keys = obter_api_keys()
        
        # Verifica se há pelo menos uma key configurada
        keys_disponiveis = [k for k, v in api_keys.items() if v]
        if not keys_disponiveis:
            return func.HttpResponse(
                json.dumps({"error": "Nenhuma API key configurada", "keys_status": {k: bool(v) for k, v in api_keys.items()}}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Consulta LLMs
        resultado = consultar_llms(
            parametro=parametro,
            candidatos=candidatos_norm,
            api_keys=api_keys
        )
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "parametro": parametro,
                "candidato_vencedor": resultado.candidato_vencedor,
                "valor_final": resultado.valor_final,
                "confianca_media": resultado.confianca_media,
                "votos": resultado.votos,
                "justificativa_consolidada": resultado.justificativa_consolidada,
                "respostas": [
                    {
                        "provider": r.provider,
                        "escolha": r.escolha,
                        "valor_normalizado": r.valor_normalizado,
                        "justificativa": r.justificativa,
                        "confianca": r.confianca,
                        "tempo_ms": r.tempo_ms,
                        "erro": r.erro
                    }
                    for r in resultado.respostas
                ]
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro no consult_llms")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )