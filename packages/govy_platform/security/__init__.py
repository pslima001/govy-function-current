# packages/govy_platform/security/__init__.py
"""
Módulo de segurança do GOVY.
Middleware de proteção: error shield, security headers, rate limiting, audit logging.
"""
from .error_shield import safe_handler
from .headers import security_headers, apply_security_headers
from .validation import validate_blob_path, validate_json_body
from .audit import audit_log

__all__ = [
    "safe_handler",
    "security_headers",
    "apply_security_headers",
    "validate_blob_path",
    "validate_json_body",
    "audit_log",
]
