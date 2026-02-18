"""CI structure check: validate critical KB pipeline files exist."""

import sys
from pathlib import Path

REQUIRED_FILES = [
    "govy/utils/juris_constants.py",
    "govy/utils/juris_regex.py",
    "govy/utils/juris_pipeline.py",
    "tests/test_juris_constants.py",
    "tests/test_juris_regex.py",
    "govy/doctrine/reader_docx.py",
    "govy/doctrine/chunker.py",
    "govy/doctrine/verbatim_classifier.py",
    "govy/doctrine/citation_extractor.py",
    "govy/doctrine/semantic.py",
    "govy/doctrine/pipeline.py",
    "tests/test_doctrine_reader.py",
    "tests/test_doctrine_chunker.py",
    "tests/test_doctrine_verbatim.py",
    "tests/test_doctrine_citation.py",
    "tests/test_doctrine_semantic.py",
]

REQUIRED_DOCS = [
    "docs/governance.md",
    "docs/dev-environment.md",
    "README.md",
]


def main() -> int:
    exit_code = 0
    for f in REQUIRED_FILES + REQUIRED_DOCS:
        p = Path(f)
        if p.exists() and p.stat().st_size > 0:
            print(f"OK:   {f}")
        else:
            print(f"FAIL: {f} {'(missing)' if not p.exists() else '(empty)'}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
