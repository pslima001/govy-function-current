# govy/security/__init__.py
"""
Módulo de segurança do GOVY.
Middleware de proteção: error shield, security headers, rate limiting, audit logging.
"""
from govy.security.error_shield import safe_handler
from govy.security.headers import security_headers, apply_security_headers
from govy.security.validation import validate_blob_path, validate_json_body
from govy.security.audit import audit_log

__all__ = [
    "safe_handler",
    "security_headers",
    "apply_security_headers",
    "validate_blob_path",
    "validate_json_body",
    "audit_log",
]
