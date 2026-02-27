"""Show stopword_hit_rate distribution of chunks rejected by HIGH_DIGIT_TOKEN_RATE."""
import json
import os
import sys
sys.path.insert(0, "C:/govy/repos/govy-function-current")
from scripts.kb.index_doctrine_v2_to_kblegal import check_gibberish_quality, build_content_from_raw
from azure.storage.blob import BlobServiceClient

conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get("AzureWebJobsStorage")
bs = BlobServiceClient.from_connection_string(conn)
cc = bs.get_container_client("kb-doutrina-processed")

digit_rejected = []  # (stopword_hit_rate, noise_score, single_char_rate, len, preview, work)

for blob in cc.list_blobs():
    data = json.loads(cc.get_blob_client(blob.name).download_blob().readall())
    sem = data.get("semantic_chunks") or []
    raw = data.get("raw_chunks") or []
    if len(sem) > 0 or len(raw) == 0:
        continue
    source = data.get("source", {})
    work = source.get("blob_name", "?").split("/")[0] if "/" in source.get("blob_name", "") else "?"
    for ch in raw:
        content = build_content_from_raw(ch)
        passed, reason, metrics = check_gibberish_quality(content)
        if reason == "HIGH_DIGIT_TOKEN_RATE":
            preview = content[:120].replace("\n", " ").strip()
            digit_rejected.append((
                metrics.get("stopword_hit_rate", 0),
                metrics.get("noise_score", metrics.get("single_char_rate", 0) + metrics.get("short_token_rate", 0)),
                metrics.get("single_char_rate", 0),
                metrics.get("digit_token_rate", 0),
                len(content),
                work,
                preview,
            ))

# Sort by stopword_hit_rate desc
digit_rejected.sort(key=lambda x: -x[0])

print(f"Total HIGH_DIGIT_TOKEN_RATE: {len(digit_rejected)}")
print()

# Distribution buckets
buckets = {">=0.40": 0, "0.35-0.39": 0, "0.30-0.34": 0, "0.25-0.29": 0, "<0.25": 0}
for sw, ns, sc, dt, ln, wk, pv in digit_rejected:
    if sw >= 0.40: buckets[">=0.40"] += 1
    elif sw >= 0.35: buckets["0.35-0.39"] += 1
    elif sw >= 0.30: buckets["0.30-0.34"] += 1
    elif sw >= 0.25: buckets["0.25-0.29"] += 1
    else: buckets["<0.25"] += 1

print("stopword_hit_rate distribution:")
for k, v in buckets.items():
    pct = v / len(digit_rejected) * 100 if digit_rejected else 0
    bar = "#" * int(pct / 2)
    print(f"  {k:>10s}: {v:4d} ({pct:5.1f}%)  {bar}")

# Top 5 with highest stopword (most likely "good" text)
print(f"\nTop 5 highest stopword_hit_rate (most likely good text):")
for sw, ns, sc, dt, ln, wk, pv in digit_rejected[:5]:
    print(f"  sw={sw:.3f} digit={dt:.3f} noise={ns:.3f} len={ln} work={wk}")
    print(f"    {pv}")

# Bottom 5 (lowest stopword = likely garbage)
print(f"\nBottom 5 lowest stopword_hit_rate (likely garbage):")
for sw, ns, sc, dt, ln, wk, pv in digit_rejected[-5:]:
    print(f"  sw={sw:.3f} digit={dt:.3f} noise={ns:.3f} len={ln} work={wk}")
    print(f"    {pv}")

# Per-work breakdown
per_work = {}
for sw, ns, sc, dt, ln, wk, pv in digit_rejected:
    per_work.setdefault(wk, []).append(sw)
print(f"\nPer-work breakdown:")
for wk, sws in sorted(per_work.items()):
    avg = sum(sws) / len(sws)
    print(f"  {wk}: {len(sws)} chunks, avg_stopword={avg:.3f}, min={min(sws):.3f}, max={max(sws):.3f}")
