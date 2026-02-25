# govy/security/audit.py
"""
Audit logging estruturado para todas as requisições HTTP.
Registra: IP, endpoint, method, status, duração, request_id.
Integra com Application Insights via logging padrão do Azure Functions.
"""
from __future__ import annotations

import logging
import time
import uuid

import azure.functions as func

logger = logging.getLogger("govy.audit")


def audit_log(
    req: func.HttpRequest,
    resp: func.HttpResponse,
    duration_ms: float | None = None,
) -> None:
    """Loga uma entrada de auditoria estruturada."""
    client_ip = (
        req.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
    )
    request_id = resp.headers.get("X-Request-ID", "n/a")

    logger.info(
        "[AUDIT] request_id=%s method=%s url=%s status=%d ip=%s duration_ms=%.1f ua=%s",
        request_id,
        req.method,
        req.url,
        resp.status_code,
        client_ip,
        duration_ms or 0.0,
        req.headers.get("User-Agent", "n/a")[:120],
    )


class AuditTimer:
    """Context manager para medir duração de uma request."""

    def __init__(self):
        self.start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.monotonic() - self.start) * 1000
