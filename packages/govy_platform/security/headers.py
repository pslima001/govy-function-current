# govy/security/headers.py
"""
Security headers aplicados a TODAS as respostas HTTP.
Protege contra: clickjacking, MIME sniffing, protocol downgrade, XSS.
"""
from __future__ import annotations

import uuid
import azure.functions as func


# Headers de segurança padrão para API (sem conteúdo HTML)
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'",
    "Cache-Control": "no-store",
    "X-XSS-Protection": "0",  # Desabilitado (CSP é superior; header legado pode causar problemas)
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def security_headers(request_id: str | None = None) -> dict:
    """Retorna dict com security headers + X-Request-ID."""
    headers = dict(_SECURITY_HEADERS)
    headers["X-Request-ID"] = request_id or str(uuid.uuid4())
    return headers


def apply_security_headers(
    resp: func.HttpResponse, req: func.HttpRequest | None = None
) -> func.HttpResponse:
    """Adiciona security headers a uma resposta existente."""
    request_id = None
    if req:
        request_id = req.headers.get("X-Request-ID")
    existing_rid = resp.headers.get("X-Request-ID")
    rid = existing_rid or request_id or str(uuid.uuid4())

    for key, value in _SECURITY_HEADERS.items():
        resp.headers[key] = value
    resp.headers["X-Request-ID"] = rid
    return resp
