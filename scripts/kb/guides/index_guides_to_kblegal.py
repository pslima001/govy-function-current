"""
GOVY - Guides -> KB Legal Index (Azure AI Search)
====================================================
Indexa chunks de guias orientativos (TCU Manual, etc.) no indice kb-legal.

Governanca:
  - doc_type="guia_tcu" forcado em runtime (nao confia no arquivo)
  - is_citable=false forcado em runtime
  - citable_reason fixo
  - Chunks com text < 300 chars nao sao indexados

Uso:
  python scripts/kb/guides/index_guides_to_kblegal.py \
    --run-id tcu_manual_2026-02-27 \
    --date-prefix 2026-02-27 \
    [--generate-embeddings true|false] \
    [--dry-run]

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
  AZURE_SEARCH_API_KEY
  AZURE_SEARCH_ENDPOINT (default: https://search-govy-kb.search.windows.net)
  OPENAI_API_KEY (se --generate-embeddings true)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ─── Config ──────────────────────────────────────────────────────────────────

STORAGE_CONTAINER = "kb-content"
AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Fields accepted by kb-legal index
INDEX_FIELDS = {
    "chunk_id", "doc_type", "source", "tribunal", "uf", "region",
    "title", "content", "citation", "year", "authority_score", "is_current",
    "effect", "secao", "procedural_stage", "holding_outcome", "remedy_type", "claim_pattern",
    "embedding",
    "is_citable", "citable_reason", "source_work",
}

BATCH_SIZE = 50
MIN_TEXT_CHARS = 300

# Governance: forced at runtime
FORCED_DOC_TYPE = "guia_tcu"
FORCED_IS_CITABLE = False
FORCED_CITABLE_REASON = "GUIA_ORIENTATIVO_NAO_NORMATIVO_USO_CHECKLIST"
AUTHORITY_SCORE = 0.50  # Orientativo: abaixo de lei (1.0), acima de raw doutrina (0.40)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_conn() -> str:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage")
    return conn


def _stage_tag_to_procedural_stage(stage_tag: str) -> str:
    """Map our stage_tag to the procedural_stage field in kb-legal."""
    mapping = {
        "planejamento": "PLANEJAMENTO",
        "edital": "EDITAL",
        "seleção": "SELECAO",
        "contrato": "CONTRATO",
        "gestão": "GESTAO",
        "governança": "GOVERNANCA",
    }
    return mapping.get(stage_tag, "NAO_CLARO")


def _stage_tag_to_secao(stage_tag: str) -> str:
    """Map stage_tag to secao (searchable facet in kb-legal)."""
    # Guides are always 'contexto_minimo' since they are reference material
    return "contexto_minimo"


def chunk_to_kb_doc(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a guide chunk to a kb-legal document with governance enforced."""
    text = chunk.get("text", "")
    chunk_id = chunk.get("chunk_id", "")

    if not text or len(text) < MIN_TEXT_CHARS:
        return None
    if not chunk_id:
        return None

    section_title = chunk.get("section_title", "")
    section_id = chunk.get("section_id", "")
    stage_tag = chunk.get("stage_tag", "")
    source_url = chunk.get("source_url", "")

    # Build citation
    citation_parts = ["TCU Manual"]
    if section_id:
        citation_parts.append(section_id)
    if section_title:
        title_short = section_title[:80]
        citation_parts.append(title_short)
    citation = " - ".join(citation_parts)

    doc: Dict[str, Any] = {
        "chunk_id": chunk_id,
        # GOVERNANCE: forced at runtime
        "doc_type": FORCED_DOC_TYPE,
        "is_citable": FORCED_IS_CITABLE,
        "citable_reason": FORCED_CITABLE_REASON,
        # Content
        "content": text,
        "title": section_title or citation,
        "citation": citation,
        "source": source_url or f"tcu_manual/{section_id}",
        "source_work": chunk.get("source_work", "tcu_manual"),
        # Classification
        "authority_score": AUTHORITY_SCORE,
        "is_current": True,
        "secao": _stage_tag_to_secao(stage_tag),
        "procedural_stage": _stage_tag_to_procedural_stage(stage_tag),
        "effect": "NAO_CLARO",
        "claim_pattern": f"doc_type={FORCED_DOC_TYPE};stage_tag={stage_tag};section={section_id}",
    }

    return doc


# ─── Embeddings ──────────────────────────────────────────────────────────────

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings in batch using OpenAI text-embedding-3-small."""
    from openai import OpenAI

    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")

    client = OpenAI(api_key=OPENAI_API_KEY)
    # Process in sub-batches of 100 (OpenAI limit is 2048)
    all_embeddings: List[List[float]] = []
    sub_batch_size = 100

    for i in range(0, len(texts), sub_batch_size):
        sub_batch = texts[i:i + sub_batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=sub_batch,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        all_embeddings.extend([d.embedding for d in sorted_data])

    return all_embeddings


# ─── Indexing ────────────────────────────────────────────────────────────────

def index_batch(docs: List[Dict[str, Any]], generate_embeddings: bool) -> Dict[str, Any]:
    """Index a batch of docs to Azure AI Search."""
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    if not AZURE_SEARCH_API_KEY:
        return {"status": "error", "indexed": 0, "failed": len(docs),
                "errors": [{"error": "AZURE_SEARCH_API_KEY missing"}]}

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

    # Filter to only INDEX_FIELDS
    documents = [{k: v for k, v in doc.items() if k in INDEX_FIELDS} for doc in docs]
    errors = []

    # Generate embeddings in batch
    if generate_embeddings and documents:
        try:
            texts = [d.get("content", "") for d in documents]
            embeddings = generate_embeddings_batch(texts)
            for i, emb in enumerate(embeddings):
                documents[i]["embedding"] = emb
        except Exception as e:
            errors.append({"error": f"Embedding batch failed: {str(e)}"})
            return {"status": "error", "indexed": 0, "failed": len(docs), "errors": errors}

    if not documents:
        return {"status": "error", "indexed": 0, "failed": len(docs), "errors": errors}

    try:
        result = search_client.upload_documents(documents)
        indexed = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        for r in result:
            if not r.succeeded:
                errors.append({"chunk_id": r.key, "error": r.error_message})
        return {"status": "success" if failed == 0 else "partial",
                "indexed": indexed, "failed": failed, "errors": errors}
    except Exception as e:
        return {"status": "error", "indexed": 0, "failed": len(documents),
                "errors": [{"error": str(e)}]}


# ─── Validation ──────────────────────────────────────────────────────────────

def run_validation(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Post-indexation validation checks."""
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    if not AZURE_SEARCH_API_KEY:
        return {"status": "skipped", "reason": "no API key"}

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

    validation = {}

    # Check 1: count by doc_type
    try:
        results = search_client.search(
            search_text="*",
            filter=f"doc_type eq '{FORCED_DOC_TYPE}'",
            top=0,
            include_total_count=True,
        )
        validation["count_guia_tcu"] = results.get_count()
    except Exception as e:
        validation["count_guia_tcu_error"] = str(e)

    # Check 2: is_citable=true should be 0
    try:
        results = search_client.search(
            search_text="*",
            filter=f"doc_type eq '{FORCED_DOC_TYPE}' and is_citable eq true",
            top=0,
            include_total_count=True,
        )
        validation["count_citable_true"] = results.get_count()
    except Exception as e:
        validation["count_citable_error"] = str(e)

    # Check 3: sample 10 chunks
    try:
        results = search_client.search(
            search_text="*",
            filter=f"doc_type eq '{FORCED_DOC_TYPE}'",
            top=10,
            select=["chunk_id", "title", "procedural_stage", "source", "is_citable"],
        )
        sample = []
        for r in results:
            sample.append({
                "chunk_id": r.get("chunk_id", ""),
                "title": (r.get("title", "") or "")[:60],
                "procedural_stage": r.get("procedural_stage", ""),
                "source": (r.get("source", "") or "")[:80],
                "is_citable": r.get("is_citable"),
            })
        validation["sample_chunks"] = sample
    except Exception as e:
        validation["sample_error"] = str(e)

    return validation


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def run_index(
    run_id: str,
    date_prefix: str,
    input_blob: Optional[str] = None,
    generate_embeddings: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute the indexation pipeline."""

    if not input_blob:
        input_blob = f"guia_tcu/processed/{date_prefix}/manual_tcu.semantic_chunks.json"

    stats = {
        "run_id": run_id,
        "date_prefix": date_prefix,
        "input_blob": input_blob,
        "chunks_loaded": 0,
        "chunks_valid": 0,
        "chunks_skipped_short": 0,
        "chunks_skipped_no_id": 0,
        "chunks_indexed": 0,
        "chunks_failed": 0,
    }

    # Load chunks from blob
    print(f"[1/4] Loading chunks from blob: {STORAGE_CONTAINER}/{input_blob}")
    from azure.storage.blob import BlobServiceClient

    conn = _get_conn()
    blob_service = BlobServiceClient.from_connection_string(conn)
    container_client = blob_service.get_container_client(STORAGE_CONTAINER)

    blob_data = container_client.get_blob_client(input_blob).download_blob().readall()
    payload = json.loads(blob_data)

    chunks = payload.get("chunks", [])
    stats["chunks_loaded"] = len(chunks)
    print(f"  Loaded {len(chunks)} chunks")

    # Map to kb-legal docs
    print(f"[2/4] Mapping to kb-legal format (governance enforced)...")
    docs: List[Dict[str, Any]] = []
    stage_dist: Dict[str, int] = {}

    for chunk in chunks:
        doc = chunk_to_kb_doc(chunk)
        if doc:
            docs.append(doc)
            stats["chunks_valid"] += 1
            ps = doc.get("procedural_stage", "NAO_CLARO")
            stage_dist[ps] = stage_dist.get(ps, 0) + 1
        else:
            text = chunk.get("text", "")
            if not chunk.get("chunk_id"):
                stats["chunks_skipped_no_id"] += 1
            elif len(text) < MIN_TEXT_CHARS:
                stats["chunks_skipped_short"] += 1

    print(f"  Valid: {stats['chunks_valid']}, Skipped short: {stats['chunks_skipped_short']}, "
          f"Skipped no ID: {stats['chunks_skipped_no_id']}")

    if dry_run:
        print(f"\n=== DRY RUN ===")
        for d in docs[:3]:
            preview = {k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)
                       for k, v in d.items()}
            print(json.dumps(preview, ensure_ascii=False, indent=2))
        if len(docs) > 3:
            print(f"  ... +{len(docs)-3} docs")
        print(f"\nTotal: {len(docs)} docs would be indexed")
        stats["dry_run"] = True
        return stats

    # Index in batches
    print(f"[3/4] Indexing {len(docs)} docs in batches of {BATCH_SIZE} (embeddings={generate_embeddings})...")
    all_errors: List[Dict] = []

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        result = index_batch(batch, generate_embeddings)

        stats["chunks_indexed"] += result.get("indexed", 0)
        stats["chunks_failed"] += result.get("failed", 0)
        all_errors.extend(result.get("errors", []))

        progress = min(i + BATCH_SIZE, len(docs))
        print(f"  Batch {i//BATCH_SIZE + 1}: {result.get('indexed', 0)} indexed, "
              f"{result.get('failed', 0)} failed | Progress: {progress}/{len(docs)}")

    # Validation
    print(f"[4/4] Running post-indexation validation...")
    validation = run_validation(stats)

    # Report
    print(f"\n{'='*60}")
    print("INDEX REPORT - TCU Manual -> kb-legal")
    print(f"{'='*60}")
    print(f"Run ID:           {run_id}")
    print(f"Chunks loaded:    {stats['chunks_loaded']}")
    print(f"Chunks valid:     {stats['chunks_valid']}")
    print(f"Chunks indexed:   {stats['chunks_indexed']}")
    print(f"Chunks failed:    {stats['chunks_failed']}")
    print(f"Skipped (short):  {stats['chunks_skipped_short']}")
    print(f"Skipped (no id):  {stats['chunks_skipped_no_id']}")
    print(f"\nProcedural stage distribution:")
    for ps, count in sorted(stage_dist.items(), key=lambda x: -x[1]):
        print(f"  {ps:20s}: {count}")

    print(f"\nValidation:")
    print(f"  doc_type='guia_tcu' count: {validation.get('count_guia_tcu', 'N/A')}")
    print(f"  is_citable=true count:     {validation.get('count_citable_true', 'N/A')} (should be 0)")

    sample = validation.get("sample_chunks", [])
    if sample:
        print(f"\n  Sample chunks (10):")
        for s in sample:
            print(f"    {s['chunk_id'][:20]}... | {s['title'][:40]} | {s['procedural_stage']} | citable={s['is_citable']}")

    if all_errors:
        print(f"\nFirst 5 errors:")
        for e in all_errors[:5]:
            print(f"  {e}")

    # Save log
    log = {
        "kind": "tcu_manual_index_log_v1",
        "run_id": run_id,
        "date_prefix": date_prefix,
        "stats": stats,
        "validation": validation,
        "errors": all_errors[:20],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    log_blob = f"guia_tcu/logs/{date_prefix}/index_log.json"
    log_json = json.dumps(log, ensure_ascii=False, indent=2)
    container_client.upload_blob(log_blob, log_json, overwrite=True)
    print(f"\nLog saved: {STORAGE_CONTAINER}/{log_blob}")

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Index TCU Manual guides to kb-legal")
    ap.add_argument("--run-id", required=True, help="Unique run identifier")
    ap.add_argument("--date-prefix", required=True, help="Date prefix (e.g. 2026-02-27)")
    ap.add_argument("--input-blob", default=None,
                     help="Override input blob path")
    ap.add_argument("--index-name", default="kb-legal",
                     help="Azure Search index name (default: kb-legal)")
    ap.add_argument("--generate-embeddings", default="true", choices=["true", "false"],
                     help="Generate OpenAI embeddings (default: true)")
    ap.add_argument("--dry-run", action="store_true",
                     help="Show what would be indexed without sending to Azure Search")
    args = ap.parse_args()

    global AZURE_SEARCH_INDEX_NAME
    AZURE_SEARCH_INDEX_NAME = args.index_name

    run_index(
        run_id=args.run_id,
        date_prefix=args.date_prefix,
        input_blob=args.input_blob,
        generate_embeddings=args.generate_embeddings.lower() == "true",
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
