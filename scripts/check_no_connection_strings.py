"""Anti-regression check: block new connection string auth in app code.

Scans govy/ and function_app.py for prohibited patterns:
  - from_connection_string(
  - DefaultEndpointsProtocol=.*AccountKey=

Allowed ONLY when the same line or the line above contains the sentinel:
  # ALLOW_CONNECTION_STRING_OK

Exit 0 if clean, exit 1 if new unauthorized usage detected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_TARGETS = [
    REPO_ROOT / "govy",
    REPO_ROOT / "function_app.py",
]

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules"}

PATTERNS = [
    re.compile(r"from_connection_string\("),
    re.compile(r"DefaultEndpointsProtocol=.*AccountKey="),
]

SENTINEL = "ALLOW_CONNECTION_STRING_OK"


def _iter_py_files():
    for target in SCAN_TARGETS:
        if target.is_file() and target.suffix == ".py":
            yield target
        elif target.is_dir():
            for p in sorted(target.rglob("*.py")):
                if not any(part in EXCLUDE_DIRS for part in p.parts):
                    yield p


def main() -> int:
    violations = []

    for filepath in _iter_py_files():
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines):
            for pattern in PATTERNS:
                if pattern.search(line):
                    # Check sentinel on same line
                    if SENTINEL in line:
                        break
                    # Check sentinel on previous line
                    if i > 0 and SENTINEL in lines[i - 1]:
                        break
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append((str(rel), i + 1, line.strip()))
                    break

    if violations:
        print("CONNECTION STRING ANTI-REGRESSION CHECK FAILED")
        print("=" * 60)
        print(f"Found {len(violations)} unauthorized usage(s):\n")
        for path, lineno, text in violations:
            print(f"  {path}:{lineno}")
            print(f"    {text}\n")
        print("To allowlist an intentional usage, add this comment")
        print("on the same line or the line above:")
        print(f"  # {SENTINEL}")
        return 1

    print("Anti-regression auth check: PASSED")
    print(f"  Scanned: govy/**/*.py + function_app.py")
    print(f"  Sentinel: {SENTINEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
