from __future__ import annotations

import os
import azure.functions as func

# Origins permitidas — configurável via env var GOVY_ALLOWED_ORIGINS (separadas por vírgula).
# Em produção: setar GOVY_ALLOWED_ORIGINS=https://stgovyparsetestsponsor.z13.web.core.windows.net
# Em dev local: localhost é incluído automaticamente quando GOVY_ENV != "production"

_PRODUCTION_ORIGINS = {
    "https://stgovyparsetestsponsor.z13.web.core.windows.net",
}

_DEV_ORIGINS = {
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:3001",
}


def _load_allowed_origins() -> set[str]:
    """Carrega origins permitidas baseado no ambiente."""
    env_origins = os.environ.get("GOVY_ALLOWED_ORIGINS", "")
    if env_origins:
        return {o.strip() for o in env_origins.split(",") if o.strip()}

    origins = set(_PRODUCTION_ORIGINS)
    if os.environ.get("GOVY_ENV", "development") != "production":
        origins |= _DEV_ORIGINS
    return origins


def get_allowed_origins() -> set[str]:
    """Retorna set de origins permitidas (recalcula a cada chamada para hot-reload de env vars)."""
    return _load_allowed_origins()


def cors_headers(req: func.HttpRequest) -> dict:
    origin = req.headers.get("Origin")
    allowed = get_allowed_origins()
    allow_origin = origin if origin in allowed else ""
    if not allow_origin:
        return {"Vary": "Origin"}
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Vary": "Origin",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS,DELETE",
        "Access-Control-Allow-Headers": "Content-Type,x-kb-admin-token,x-functions-key",
        "Access-Control-Max-Age": "86400",
    }


def cors_preflight(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("", status_code=204, headers=cors_headers(req))
