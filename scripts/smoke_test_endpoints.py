"""Post-deploy smoke tests for Azure Function endpoints.

Tests:
  1. GET /api/ping?code={key}             -> 200, body contains "pong"
  2. GET /api/dicionario?stats=true&code={key} -> 200, JSON "success": true

Env vars:
  BASE_URL  - e.g. https://func-govy-parse-test-....azurewebsites.net
  FUNC_KEY  - Azure Functions function key

Retries: 3 attempts with 10s/20s/30s backoff (cold start tolerance)
Timeout: 15s per request
Exit: 0 on success (or soft-skip if env vars missing), 1 on failure
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
FUNC_KEY = os.environ.get("FUNC_KEY", "")

TIMEOUT = 15
BACKOFF = [10, 20, 30]


def _get(url: str) -> tuple[int, str]:
    """GET request returning (status_code, body). Raises on network error."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body


def _test_with_retries(name: str, url: str, check_fn) -> bool:
    """Run a test with retries. Returns True on success."""
    for attempt in range(len(BACKOFF) + 1):
        try:
            status, body = _get(url)
            ok, reason = check_fn(status, body)
            if ok:
                print(f"  PASS: {name} (status={status})")
                return True
            print(f"  FAIL: {name} attempt {attempt + 1} - {reason}")
        except Exception as e:
            print(f"  FAIL: {name} attempt {attempt + 1} - {e}")
            status, body = 0, ""

        if attempt < len(BACKOFF):
            wait = BACKOFF[attempt]
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)

    # Final failure diagnostics
    print(f"  FAILED after {len(BACKOFF) + 1} attempts: {name}")
    print(f"  URL: {url}")
    print(f"  Last status: {status}")
    print(f"  Last body (2KB): {body[:2048]}")
    return False


def check_ping(status: int, body: str) -> tuple[bool, str]:
    if status != 200:
        return False, f"status={status}, expected 200"
    if "pong" not in body.lower():
        return False, f"body missing 'pong': {body[:200]}"
    return True, ""


def check_dicionario(status: int, body: str) -> tuple[bool, str]:
    if status != 200:
        return False, f"status={status}, expected 200"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, f"invalid JSON: {body[:200]}"
    if not data.get("success"):
        return False, f"success!=true: {body[:200]}"
    return True, ""


def main() -> int:
    if not BASE_URL or not FUNC_KEY:
        print("WARN: BASE_URL or FUNC_KEY not set. Skipping smoke tests.")
        return 0

    print(f"Smoke tests against: {BASE_URL}")
    print(f"Function key: {'*' * 8}...{FUNC_KEY[-4:]}" if len(FUNC_KEY) > 4 else "")

    tests = [
        ("ping", f"{BASE_URL}/api/ping?code={FUNC_KEY}", check_ping),
        ("dicionario stats", f"{BASE_URL}/api/dicionario?stats=true&code={FUNC_KEY}", check_dicionario),
    ]

    results = []
    for name, url, check_fn in tests:
        ok = _test_with_retries(name, url, check_fn)
        results.append((name, ok))

    print()
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        failed = [name for name, ok in results if not ok]
        print(f"FAILED: {', '.join(failed)}")
        return 1

    print("All smoke tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
