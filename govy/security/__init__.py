# govy/security/__init__.py — COMPAT SHIM (Fase 3 restructuring)
# Canonical location: packages/govy_platform/security/
"""Compat layer — redireciona para packages.govy_platform.security."""
from packages.govy_platform.security import (  # noqa: F401
    safe_handler,
    security_headers,
    apply_security_headers,
    validate_blob_path,
    validate_json_body,
    audit_log,
)

__all__ = [
    "safe_handler",
    "security_headers",
    "apply_security_headers",
    "validate_blob_path",
    "validate_json_body",
    "audit_log",
]
