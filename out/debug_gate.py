"""Debug OCR quality gate metrics on known-good and known-bad chunks."""
import json
import os
import re
import sys
sys.path.insert(0, "C:/govy/repos/govy-function-current")
from scripts.kb.index_doctrine_v2_to_kblegal import check_gibberish_quality, build_content_from_raw
from azure.storage.blob import BlobServiceClient

conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get("AzureWebJobsStorage")
bs = BlobServiceClient.from_connection_string(conn)
cc = bs.get_container_client("kb-doutrina-processed")

# Sample blobs: mix of known-good and known-bad from our earlier inspection
SAMPLE_BLOBS = [
    # #2 jacoby (expected: clean)
    "licitacao/licitacao/03622fa789995b0e02b80bb12acc1d7ee1d8e37d5bb7178dfdfdca200d3ac0df.json",
    # #4 jacoby (expected: clean, IN SGD/ME 94/2022)
    "licitacao/licitacao/07063030b15d4d7464213a43f4d29dca539cf67ef0ba451ad5daf46d55f9f2bb.json",
    # #7 dalenogare (expected: clean)
    "licitacao/licitacao/087f0de7ad5277e363dd7cd0f48118063088ac39dc4ac5025ee6e1044feecfa2.json",
    # #3 marcal (expected: noisy - 36 chunks)
    "licitacao/licitacao/03857002d320d1b8f5853d09174ae0f080ea6b94e44765c4cc201245a0346389.json",
    # #5 marcal (expected: noisy - jurisprudencia garbage)
    "licitacao/licitacao/074dcc6e97e1b52f572bf969641d6846cf7fd30289ad05ec7ebd1c549b361368.json",
]

for blob_name in SAMPLE_BLOBS:
    data = json.loads(cc.get_blob_client(blob_name).download_blob().readall())
    source = data.get("source", {})
    work = source.get("blob_name", "?").split("/")[0] if "/" in source.get("blob_name", "") else "?"
    raw = data.get("raw_chunks") or []

    print(f"\n{'='*70}")
    print(f"BLOB: {blob_name[-70:]}")
    print(f"work={work}  raw_chunks={len(raw)}")

    passed_count = 0
    for i, ch in enumerate(raw[:5]):  # First 5 chunks only
        content = build_content_from_raw(ch)
        ok, reason, metrics = check_gibberish_quality(content)
        status = "PASS" if ok else f"FAIL({reason})"
        if ok:
            passed_count += 1
        print(f"  chunk[{i}] {status}")
        print(f"    len={len(content)}  metrics={json.dumps(metrics)}")
        # Show first 120 chars
        preview = content[:120].replace("\n", " ")
        print(f"    preview: {preview}")

    if len(raw) > 5:
        # Check rest silently
        for i, ch in enumerate(raw[5:], start=5):
            content = build_content_from_raw(ch)
            ok, reason, metrics = check_gibberish_quality(content)
            if ok:
                passed_count += 1
        print(f"  ... ({len(raw)-5} more chunks checked silently)")
    print(f"  TOTAL: {passed_count}/{len(raw)} passed")
