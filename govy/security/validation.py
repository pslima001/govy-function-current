# govy/security/validation.py
"""
Validação e sanitização de inputs.
Previne: path traversal, injection, payloads oversized.
"""
from __future__ import annotations

import json
import re
from typing import Any

import azure.functions as func

# Tamanho máximo de body (50 MB — editais podem ser grandes)
MAX_BODY_BYTES = 50 * 1024 * 1024

# Pattern para blob paths válidos: alfanuméricos, hifens, underscores, barras, pontos
_SAFE_BLOB_PATH = re.compile(r"^[a-zA-Z0-9\-_/\.]+$")

# Sequências perigosas em blob paths
_DANGEROUS_PATTERNS = ["..", "//", "\\", "\x00", "%00", "%2e%2e"]


def validate_blob_path(path: str | None) -> tuple[bool, str]:
    """
    Valida um blob path.
    Retorna (is_valid, error_message).
    """
    if not path:
        return False, "blob_path is required"
    if len(path) > 1024:
        return False, "blob_path too long (max 1024 chars)"
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in path.lower():
            return False, f"blob_path contains forbidden pattern"
    if not _SAFE_BLOB_PATH.match(path):
        return False, "blob_path contains invalid characters"
    return True, ""


def validate_json_body(
    req: func.HttpRequest, max_bytes: int = MAX_BODY_BYTES
) -> tuple[dict[str, Any] | None, func.HttpResponse | None]:
    """
    Extrai e valida JSON body de uma request.
    Retorna (parsed_body, None) em sucesso, ou (None, error_response) em falha.
    """
    body = req.get_body()
    if len(body) > max_bytes:
        return None, func.HttpResponse(
            json.dumps({"error": f"Body too large (max {max_bytes // (1024*1024)} MB)"}),
            status_code=413,
            mimetype="application/json",
        )
    if not body:
        return None, func.HttpResponse(
            json.dumps({"error": "Request body is empty"}),
            status_code=400,
            mimetype="application/json",
        )
    try:
        parsed = req.get_json()
    except ValueError:
        return None, func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            status_code=400,
            mimetype="application/json",
        )
    if not isinstance(parsed, dict):
        return None, func.HttpResponse(
            json.dumps({"error": "JSON body must be an object"}),
            status_code=400,
            mimetype="application/json",
        )
    return parsed, None
