"""Inspect real encoding of raw_chunks in empty blobs (semantic_chunks=0)."""
import json
import os
from collections import Counter
from azure.storage.blob import BlobServiceClient

conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get("AzureWebJobsStorage")
bs = BlobServiceClient.from_connection_string(conn)
cc = bs.get_container_client("kb-doutrina-processed")

count = 0
for blob in cc.list_blobs():
    data = json.loads(cc.get_blob_client(blob.name).download_blob().readall())
    sem = data.get("semantic_chunks") or []
    raw = data.get("raw_chunks") or []
    if len(sem) == 0 and len(raw) > 0:
        count += 1
        source = data.get("source", {})
        work = source.get("blob_name", "?").split("/")[0] if "/" in source.get("blob_name", "") else "?"

        # Concatenate all raw text for this blob
        all_text = "\n".join((ch.get("content_raw") or "") for ch in raw)

        fffd = all_text.count("\uFFFD")
        cent = all_text.count("\u00A2")

        # Top non-ASCII chars
        non_ascii = [c for c in all_text if ord(c) > 127]
        top_non_ascii = Counter(non_ascii).most_common(15)

        print(f"=== [{count}] {blob.name}")
        print(f"    work={work}  raw_chunks={len(raw)}  total_chars={len(all_text)}")
        print(f"    U+FFFD (replacement): {fffd}")
        print(f"    U+00A2 (cent sign):   {cent}")
        print(f"    top non-ASCII:")
        for ch, cnt in top_non_ascii:
            print(f"      U+{ord(ch):04X} {repr(ch):6s} x{cnt:5d}  ({cnt/len(all_text)*100:.2f}%)")

        # repr of first 300 chars of first chunk
        first_text = (raw[0].get("content_raw") or "")[:300]
        print(f"    repr(chunk[0][:300]):")
        print(f"      {repr(first_text)}")
        print()

        if count >= 5:
            break
