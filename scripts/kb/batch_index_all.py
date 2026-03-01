import os, sys
sys.path.insert(0, r"C:\govy\repos\govy-function-current")
from azure.storage.blob import BlobServiceClient

conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
bs = BlobServiceClient.from_connection_string(conn)
client = bs.get_container_client("kb-doutrina-processed")
blobs = sorted([b.name for b in client.list_blobs() if b.name.endswith(".json")])
print(f"Total: {len(blobs)} blobs")

total_ok = 0
total_fail = 0
for i, b in enumerate(blobs, 1):
    print(f"\n[{i}/{len(blobs)}] {b}")
    ret = os.system(f'python scripts/kb/index_doctrine_v2_to_kblegal.py --processed-blob "{b}" --generate-embeddings true')
    if ret == 0:
        total_ok += 1
    else:
        total_fail += 1

print(f"\n{'='*50}")
print(f"BLOBS OK:   {total_ok}")
print(f"BLOBS FAIL: {total_fail}")
print(f"{'='*50}")