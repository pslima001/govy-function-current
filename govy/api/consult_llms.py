# govy/api/consult_llms.py
"""
Handler para consulta a multiplas LLMs para validacao de candidatos.
"""
import json
import logging
import azure.functions as func

logger = logging.getLogger(__name__)

def handle_consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    """
    Consulta multiplas LLMs para escolher o melhor candidato.
    
    Request body:
    {
        "parametro": "e001",
        "candidatos": [
            {"value": "5 dias", "score": 12, "context": "prazo de entrega de 5 dias"},
            {"value": "30 dias", "score": 10, "context": "prazo de 30 dias corridos"}
        ],
        "providers": ["openai", "anthropic", "groq"]  // opcional
    }
    
    Response:
    {
        "status": "success",
        "parametro": "e001",
        "candidato_vencedor": 1,
        "valor_final": "5 dias",
        "votos": {"openai": 1, "anthropic": 1, "groq": 1},
        "confianca_media": 0.85,
        "respostas": [...]
    }
    """
    try:
        # Parse request
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "JSON invalido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        parametro = body.get("parametro")
        candidatos = body.get("candidatos", [])
        providers = body.get("providers")  # opcional
        
        if not parametro:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Campo 'parametro' obrigatorio"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not candidatos:
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "parametro": parametro,
                    "candidato_vencedor": 0,
                    "valor_final": None,
                    "votos": {},
                    "confianca_media": 0.0,
                    "mensagem": "Nenhum candidato fornecido"
                }),
                status_code=200,
                mimetype="application/json"
            )
        
        # Import aqui para lazy loading
        from govy.utils.multi_llm import consultar_llms, obter_api_keys
        
        # Obter API keys do ambiente
        api_keys = obter_api_keys()
        
        # Consultar LLMs
        resultado = consultar_llms(
            parametro=parametro,
            candidatos=candidatos,
            api_keys=api_keys,
            providers=providers
        )
        
        # Formatar resposta
        response_data = {
            "status": "success",
            "parametro": parametro,
            "candidato_vencedor": resultado.candidato_vencedor,
            "valor_final": resultado.valor_final,
            "votos": resultado.votos,
            "confianca_media": resultado.confianca_media,
            "justificativa_consolidada": resultado.justificativa_consolidada,
            "respostas": [
                {
                    "provider": r.provider,
                    "escolha": r.escolha,
                    "valor_normalizado": r.valor_normalizado,
                    "justificativa": r.justificativa,
                    "confianca": r.confianca,
                    "erro": r.erro,
                    "tempo_ms": r.tempo_ms
                }
                for r in resultado.respostas
            ]
        }
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Erro em consult_llms")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
