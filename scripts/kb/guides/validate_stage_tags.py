"""
GOVY - Validate guia_tcu stage_tags in kb-legal index
=======================================================
Queries the index and verifies all procedural_stage values
match the frozen enum. Fails (exit 1) if any value is outside.

Uso:
  AZURE_SEARCH_API_KEY=... AZURE_SEARCH_ENDPOINT=... \
    python scripts/kb/guides/validate_stage_tags.py

Exit codes:
  0 = all values match enum
  1 = validation failed (unknown values found)
"""

import os
import sys

# Allow import from same directory
sys.path.insert(0, os.path.dirname(__file__))
from stage_tags import PROCEDURAL_STAGES, PROCEDURAL_STAGE_TO_STAGE_TAG


def main():
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")
    if not api_key:
        print("ERROR: AZURE_SEARCH_API_KEY not set")
        sys.exit(1)

    client = SearchClient(
        endpoint=endpoint,
        index_name=os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal"),
        credential=AzureKeyCredential(api_key),
    )

    # Collect all distinct procedural_stage values for guia_tcu
    stage_counts = {}
    skip = 0
    batch_size = 1000
    while True:
        results = client.search(
            search_text="*",
            filter="doc_type eq 'guia_tcu'",
            select=["procedural_stage"],
            top=batch_size,
            skip=skip,
        )
        batch = list(results)
        if not batch:
            break
        for r in batch:
            ps = r.get("procedural_stage", "NULL")
            stage_counts[ps] = stage_counts.get(ps, 0) + 1
        skip += batch_size

    total = sum(stage_counts.values())

    # Validate
    known = set()
    unknown = set()
    for ps in stage_counts:
        if ps in PROCEDURAL_STAGES:
            known.add(ps)
        else:
            unknown.add(ps)

    missing = PROCEDURAL_STAGES - set(stage_counts.keys())

    # Report
    print("=" * 60)
    print("STAGE TAG VALIDATION - guia_tcu")
    print("=" * 60)
    print(f"Total chunks:    {total}")
    print(f"Enum size:       {len(PROCEDURAL_STAGES)}")
    print(f"Distinct values: {len(stage_counts)}")
    print()
    print("Distribution:")
    for ps, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
        tag = PROCEDURAL_STAGE_TO_STAGE_TAG.get(ps, "???")
        status = "OK" if ps in PROCEDURAL_STAGES else "UNKNOWN"
        pct = 100 * count / max(total, 1)
        print(f"  {ps:20s} ({tag:15s}): {count:5d} ({pct:5.1f}%) [{status}]")

    if missing:
        print(f"\nMissing from index (in enum but 0 chunks):")
        for ps in sorted(missing):
            print(f"  {ps}")

    if unknown:
        print(f"\nUNKNOWN values (NOT in enum):")
        for ps in sorted(unknown):
            print(f"  {ps}: {stage_counts[ps]} chunks")
        print(f"\nVALIDATION FAILED: {len(unknown)} unknown values found")
        sys.exit(1)
    else:
        print(f"\nVALIDATION PASSED: all {len(known)} values match enum")
        sys.exit(0)


if __name__ == "__main__":
    main()
