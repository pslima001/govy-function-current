"""Sample 10 empty blobs (semantic_chunks=0, raw_chunks>0) with preview."""
import json
import os
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
        print(f"--- [{count}] {blob.name}")
        print(f"    work={work}  raw_chunks={len(raw)}")
        for i, ch in enumerate(raw):
            txt = (ch.get("content_raw") or "")[:180].replace("\n", " ").strip()
            print(f"    chunk[{i}]: {txt}")
        print()
        if count >= 10:
            break
