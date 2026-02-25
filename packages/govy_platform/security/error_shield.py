# govy/security/error_shield.py
"""
Decorator que captura exceções e retorna erro genérico ao cliente.
Traceback completo é logado internamente (Application Insights), NUNCA exposto na resposta.
"""
from __future__ import annotations

import functools
import json
import logging
import traceback
import uuid

import azure.functions as func

logger = logging.getLogger("govy.security")


def safe_handler(fn):
    """
    Decorator para HTTP handlers.
    - Captura qualquer exceção não tratada
    - Loga traceback completo com request_id para correlação
    - Retorna JSON genérico ao cliente (sem detalhes internos)
    """

    @functools.wraps(fn)
    def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
        request_id = req.headers.get("X-Request-ID") or str(uuid.uuid4())
        try:
            return fn(req, *args, **kwargs)
        except Exception:
            logger.error(
                "[UNHANDLED] request_id=%s endpoint=%s error:\n%s",
                request_id,
                fn.__name__,
                traceback.format_exc(),
            )
            body = json.dumps(
                {
                    "error": "Internal server error",
                    "request_id": request_id,
                    "hint": "Erro interno. Use o request_id para suporte.",
                },
                ensure_ascii=False,
            )
            return func.HttpResponse(
                body,
                status_code=500,
                mimetype="application/json",
                headers={"X-Request-ID": request_id},
            )

    return wrapper
