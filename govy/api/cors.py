from __future__ import annotations
import azure.functions as func

ALLOWED_ORIGINS = {
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:3001",
    "https://stgovyparsetestsponsor.z13.web.core.windows.net",
}

def cors_headers(req: func.HttpRequest) -> dict:
    origin = req.headers.get("Origin")
    allow_origin = origin if origin in ALLOWED_ORIGINS else "http://localhost:8080"
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Vary": "Origin",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS,DELETE",
        "Access-Control-Allow-Headers": "Content-Type,x-kb-admin-token,x-functions-key",
        "Access-Control-Max-Age": "86400",
    }

def cors_preflight(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("", status_code=204, headers=cors_headers(req))
