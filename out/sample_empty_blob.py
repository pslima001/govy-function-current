"""Fetch one 'empty' blob (no semantic_chunks, has raw_chunks) and dump it."""
import json
import os
from azure.storage.blob import BlobServiceClient

conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get("AzureWebJobsStorage")
bs = BlobServiceClient.from_connection_string(conn)
cc = bs.get_container_client("kb-doutrina-processed")

for blob in cc.list_blobs():
    data = json.loads(cc.get_blob_client(blob.name).download_blob().readall())
    sem = data.get("semantic_chunks") or []
    raw = data.get("raw_chunks") or []
    if len(sem) == 0 and len(raw) > 0:
        print(f"BLOB: {blob.name}")
        print(f"semantic_chunks: {len(sem)}  |  raw_chunks: {len(raw)}")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:8000])
        break
