"""
Validate doctrine indexation in kb-legal Azure AI Search.
"""
import json
import os
import sys
import requests

ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
API_VERSION = "2024-07-01"


def search(params):
    url = f"{ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    resp = requests.post(url, headers=headers, json=params)
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text[:500]}")
        sys.exit(1)
    return resp.json()


def main():
    if not API_KEY:
        print("ERROR: AZURE_SEARCH_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("VALIDATION: kb-legal doctrine indexation")
    print("=" * 60)

    # 1. Total doutrina count
    r = search({"search": "*", "filter": "doc_type eq 'doutrina'", "top": 0, "count": True})
    total = r.get("@odata.count", "?")
    print(f"\n1. Total doutrina docs: {total}")

    # 2. Facet by source_work
    r = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina'",
        "facets": ["source_work,count:10"],
        "top": 0,
        "count": True,
    })
    print(f"\n2. Facet source_work:")
    facets = r.get("@search.facets", {}).get("source_work", [])
    for f in facets:
        print(f"   {f['value']}: {f['count']}")
    # Also show how many have null source_work (old docs)
    r2 = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina' and source_work eq null",
        "top": 0,
        "count": True,
    })
    null_count = r2.get("@odata.count", "?")
    print(f"   (null/old docs): {null_count}")

    # 3. is_citable distribution
    r_true = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina' and is_citable eq true",
        "top": 0,
        "count": True,
    })
    r_false = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina' and is_citable eq false",
        "top": 0,
        "count": True,
    })
    r_null = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina' and is_citable eq null",
        "top": 0,
        "count": True,
    })
    print(f"\n3. is_citable distribution:")
    print(f"   true:  {r_true.get('@odata.count', '?')}")
    print(f"   false: {r_false.get('@odata.count', '?')}")
    print(f"   null:  {r_null.get('@odata.count', '?')}")

    # 4. Facet by citable_reason
    r = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina'",
        "facets": ["citable_reason,count:10"],
        "top": 0,
    })
    print(f"\n4. Facet citable_reason:")
    facets = r.get("@search.facets", {}).get("citable_reason", [])
    for f in facets:
        print(f"   {f['value']}: {f['count']}")

    # 5. Sample citable marcal chunk
    r = search({
        "search": "*",
        "filter": "doc_type eq 'doutrina' and is_citable eq true and source_work eq 'marcal'",
        "top": 1,
        "select": "chunk_id,title,source_work,is_citable,citable_reason,authority_score,secao,procedural_stage",
    })
    docs = r.get("value", [])
    if docs:
        print(f"\n5. Sample citable marcal chunk:")
        print(json.dumps(docs[0], indent=2, ensure_ascii=False))
    else:
        print("\n5. No citable marcal chunks found!")

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
