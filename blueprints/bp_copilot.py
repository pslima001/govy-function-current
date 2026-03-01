# blueprints/bp_copilot.py
"""
Blueprint do Copiloto Jurídico GOVY.

Endpoints:
  POST /api/copilot/chat           — chat principal
  POST /api/copilot/explain-check  — explicação de item do checklist
  GET  /api/copilot/ping           — health check
"""
import json
import logging

import azure.functions as func

bp = func.Blueprint()
logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
}


@bp.function_name(name="copilot_ping")
@bp.route(route="copilot/ping", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def copilot_ping(req: func.HttpRequest) -> func.HttpResponse:
    from govy.copilot.config import LLM_ENABLED, LLM_PROVIDER, get_active_model
    return func.HttpResponse(
        json.dumps({
            "status": "ok",
            "module": "copilot",
            "llm_enabled": LLM_ENABLED,
            "llm_provider": LLM_PROVIDER,
            "llm_model": get_active_model() if LLM_ENABLED else None,
        }),
        status_code=200,
        headers=CORS_HEADERS,
    )


@bp.function_name(name="copilot_chat")
@bp.route(route="copilot/chat", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def copilot_chat(req: func.HttpRequest) -> func.HttpResponse:
    # CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=CORS_HEADERS)

    try:
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "JSON inválido"}),
                status_code=400,
                headers=CORS_HEADERS,
            )

        user_text = body.get("user_text") or body.get("message") or body.get("query", "")
        if not user_text:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "user_text é obrigatório"}),
                status_code=400,
                headers=CORS_HEADERS,
            )

        context = body.get("context", {})

        from govy.copilot.handler import handle_chat

        output = handle_chat(user_text=user_text, context=context)

        return func.HttpResponse(
            json.dumps(output.to_json_response(), ensure_ascii=False, default=str),
            status_code=200,
            headers=CORS_HEADERS,
        )

    except Exception as e:
        logger.exception("Erro no copilot/chat")
        return func.HttpResponse(
            json.dumps({"status": "error", "error": str(e)}),
            status_code=500,
            headers=CORS_HEADERS,
        )


@bp.function_name(name="copilot_explain_check")
@bp.route(route="copilot/explain-check", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def copilot_explain_check(req: func.HttpRequest) -> func.HttpResponse:
    """Explica um item do checklist de conformidade."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=CORS_HEADERS)

    try:
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "JSON inválido"}),
                status_code=400,
                headers=CORS_HEADERS,
            )

        check_id = body.get("check_id", "")
        edital_id = body.get("edital_id", "")

        if not check_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "check_id é obrigatório"}),
                status_code=400,
                headers=CORS_HEADERS,
            )
        if not edital_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "edital_id é obrigatório"}),
                status_code=400,
                headers=CORS_HEADERS,
            )

        context = body.get("context", {})

        from govy.copilot.handler import explain_check

        output = explain_check(check_id=check_id, edital_id=edital_id, context=context)

        return func.HttpResponse(
            json.dumps(output.to_json_response(), ensure_ascii=False, default=str),
            status_code=200,
            headers=CORS_HEADERS,
        )

    except Exception as e:
        logger.exception("Erro no copilot/explain-check")
        return func.HttpResponse(
            json.dumps({"status": "error", "error": str(e)}),
            status_code=500,
            headers=CORS_HEADERS,
        )
