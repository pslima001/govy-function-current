"""Export TCU inventory from Azure AI Search (kb-legal index).

Extracts unique TCU documents (deduped by title), saves inventory JSON.
Does NOT download PDFs — only creates the inventory for future scraping.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://search-govy-kb.search.windows.net"
INDEX_NAME = "kb-legal"
OUTPUT_PATH = "outputs/tcu_inventory.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_api_key() -> str:
    key = os.environ.get("AZURE_SEARCH_API_KEY", "")
    if key:
        return key
    # Fall back to az cli
    import subprocess

    result = subprocess.run(
        [
            "az",
            "search",
            "admin-key",
            "show",
            "--resource-group",
            "rg-govy-parse-test-sponsor",
            "--service-name",
            "search-govy-kb",
            "--query",
            "primaryKey",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get search API key: {result.stderr}")
    return result.stdout.strip()


def _search_tcu_chunks(api_key: str) -> list[dict]:
    """Paginate through all TCU chunks in the search index."""
    import urllib.request

    all_docs: list[dict] = []
    skip = 0
    page_size = 1000

    while True:
        url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version=2024-07-01"
        payload = {
            "filter": "tribunal eq 'TCU'",
            "select": "chunk_id,doc_type,source,tribunal,title,citation,year,secao,effect,procedural_stage",
            "top": page_size,
            "skip": skip,
            "count": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "api-key": api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        docs = result.get("value", [])
        if not docs:
            break

        all_docs.extend(docs)
        total = result.get("@odata.count", 0)
        logger.info(f"Fetched {len(all_docs)}/{total} chunks")

        if len(all_docs) >= total:
            break
        skip += page_size

    return all_docs


def _dedup_by_title(chunks: list[dict]) -> list[dict]:
    """Group chunks by title (= unique document) and extract doc-level info."""
    docs: dict[str, dict] = {}
    for chunk in chunks:
        title = chunk.get("title", "")
        if not title:
            continue
        if title not in docs:
            docs[title] = {
                "title": title,
                "source": chunk.get("source"),
                "tribunal": chunk.get("tribunal"),
                "year": chunk.get("year"),
                "citation_sample": chunk.get("citation"),
                "effects": set(),
                "procedural_stages": set(),
                "secoes": set(),
                "chunk_count": 0,
            }
        doc = docs[title]
        doc["chunk_count"] += 1
        if chunk.get("effect"):
            doc["effects"].add(chunk["effect"])
        if chunk.get("procedural_stage"):
            doc["procedural_stages"].add(chunk["procedural_stage"])
        if chunk.get("secao"):
            doc["secoes"].add(chunk["secao"])

    # Convert sets to sorted lists for JSON serialization
    result = []
    for doc in docs.values():
        doc["effects"] = sorted(doc["effects"])
        doc["procedural_stages"] = sorted(doc["procedural_stages"])
        doc["secoes"] = sorted(doc["secoes"])
        result.append(doc)

    return sorted(result, key=lambda d: d["title"])


def main() -> int:
    api_key = _get_api_key()
    logger.info("Fetching TCU chunks from Azure AI Search...")
    chunks = _search_tcu_chunks(api_key)
    logger.info(f"Total TCU chunks: {len(chunks)}")

    docs = _dedup_by_title(chunks)
    logger.info(f"Unique TCU documents: {len(docs)}")

    # Stats
    effects = {}
    stages = {}
    for doc in docs:
        for e in doc["effects"]:
            effects[e] = effects.get(e, 0) + 1
        for s in doc["procedural_stages"]:
            stages[s] = stages.get(s, 0) + 1

    inventory = {
        "kind": "tcu_inventory",
        "generated_at": _utc_now_iso(),
        "source": f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}",
        "summary": {
            "total_chunks": len(chunks),
            "unique_documents": len(docs),
            "effects_distribution": dict(sorted(effects.items(), key=lambda x: -x[1])),
            "procedural_stages_distribution": dict(sorted(stages.items(), key=lambda x: -x[1])),
        },
        "documents": docs,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)
    logger.info(f"Inventory saved to {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
