# govy/security/rate_limit.py
"""
Rate limiter in-memory para Azure Functions (Consumption Plan).

Nota: no Consumption Plan, instâncias são efêmeras e independentes.
O rate limit é POR INSTÂNCIA, não global. Isso é uma limitação aceitável:
- Já reduz abuso significativamente (cada instância bloqueia seus próprios abusadores)
- Para rate limiting global, seria necessário Redis ou APIM (custo adicional)

Algoritmo: Fixed Window Counter (simples e eficiente para este caso).
"""
from __future__ import annotations

import functools
import json
import logging
import threading
import time
from typing import Callable

import azure.functions as func

logger = logging.getLogger("govy.security")

# Lock para thread-safety (Azure Functions pode ter múltiplas threads)
_lock = threading.Lock()

# Estrutura: { "endpoint:ip": (count, window_start) }
_counters: dict[str, tuple[int, float]] = {}

# Limpeza periódica de entries antigas
_last_cleanup = 0.0
_CLEANUP_INTERVAL = 300  # 5 minutos


def _cleanup_expired(window_seconds: int) -> None:
    """Remove counters expirados para não vazar memória."""
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    expired = [
        k for k, (_, start) in _counters.items() if now - start > window_seconds * 2
    ]
    for k in expired:
        _counters.pop(k, None)


def rate_limit(max_calls: int = 30, window_seconds: int = 60) -> Callable:
    """
    Decorator de rate limiting por IP.

    Args:
        max_calls: máximo de chamadas por janela
        window_seconds: duração da janela em segundos

    Defaults: 30 chamadas por minuto (generoso para uso normal).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
            client_ip = (
                req.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
            )
            key = f"{fn.__name__}:{client_ip}"
            now = time.monotonic()

            with _lock:
                _cleanup_expired(window_seconds)
                count, window_start = _counters.get(key, (0, now))

                # Nova janela?
                if now - window_start >= window_seconds:
                    count = 0
                    window_start = now

                count += 1
                _counters[key] = (count, window_start)

            if count > max_calls:
                remaining = int(window_seconds - (now - window_start))
                logger.warning(
                    "[RATE_LIMIT] ip=%s endpoint=%s count=%d limit=%d",
                    client_ip,
                    fn.__name__,
                    count,
                    max_calls,
                )
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Rate limit exceeded",
                            "retry_after_seconds": max(remaining, 1),
                        }
                    ),
                    status_code=429,
                    mimetype="application/json",
                    headers={
                        "Retry-After": str(max(remaining, 1)),
                    },
                )

            return fn(req, *args, **kwargs)

        return wrapper

    return decorator
