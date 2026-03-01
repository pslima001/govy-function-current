"""
Add governance fields (is_citable, citable_reason, source_work) to kb-legal index.
Idempotent: skips fields that already exist.
Saves backup of current schema before modifying.
"""
import json
import os
import sys
import requests
from datetime import datetime

ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
API_VERSION = "2024-07-01"

OUT_DIR = os.path.join(os.path.dirname(__file__))

FIELDS_TO_ADD = [
    {
        "name": "is_citable",
        "type": "Edm.Boolean",
        "filterable": True,
        "facetable": True,
        "sortable": False,
        "searchable": False,
        "retrievable": True,
    },
    {
        "name": "citable_reason",
        "type": "Edm.String",
        "filterable": True,
        "facetable": True,
        "sortable": False,
        "searchable": False,
        "retrievable": True,
    },
    {
        "name": "source_work",
        "type": "Edm.String",
        "filterable": True,
        "facetable": True,
        "sortable": False,
        "searchable": False,
        "retrievable": True,
    },
]


def main():
    if not API_KEY:
        print("ERROR: AZURE_SEARCH_API_KEY not set")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }

    # 1. GET current index schema
    url = f"{ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}"
    print(f"GET {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: GET failed with {resp.status_code}: {resp.text}")
        sys.exit(1)

    schema = resp.json()
    print(f"Current index has {len(schema.get('fields', []))} fields")

    # 2. Save backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(OUT_DIR, f"kb_legal_schema_backup_{ts}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"Backup saved to {backup_path}")

    # 3. Check which fields already exist
    existing_names = {f["name"] for f in schema.get("fields", [])}
    fields_added = []
    fields_skipped = []

    for field_def in FIELDS_TO_ADD:
        if field_def["name"] in existing_names:
            fields_skipped.append(field_def["name"])
        else:
            schema["fields"].append(field_def)
            fields_added.append(field_def["name"])

    if not fields_added:
        print(f"All fields already exist: {fields_skipped}")
        print("Nothing to do.")
        return

    print(f"Fields to add: {fields_added}")
    if fields_skipped:
        print(f"Fields already exist (skipped): {fields_skipped}")

    # 4. PUT updated schema
    # Remove @odata fields that cause issues on PUT
    for key in list(schema.keys()):
        if key.startswith("@odata"):
            del schema[key]

    put_url = f"{ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}"
    print(f"\nPUT {put_url} (adding {len(fields_added)} fields)")
    resp = requests.put(put_url, headers=headers, json=schema)

    if resp.status_code in (200, 201, 204):
        print(f"SUCCESS: Index updated. Status {resp.status_code}")
        updated = resp.json()
        print(f"Updated index now has {len(updated.get('fields', []))} fields")
    else:
        print(f"ERROR: PUT failed with {resp.status_code}")
        print(resp.text[:1000])
        sys.exit(1)


if __name__ == "__main__":
    main()
