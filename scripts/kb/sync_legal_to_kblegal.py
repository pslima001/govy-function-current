"""
GOVY - Legal Chunks (Postgres) -> KB Legal Index (Azure AI Search) Sync
========================================================================
Sincroniza chunks de legislacao do Postgres govy_legal para o indice kb-legal.

Legislacao e sempre citavel (is_citable=true) — e lei federal vigente.

Uso:
  python scripts/kb/sync_legal_to_kblegal.py [--dry-run] [--limit N] [--generate-embeddings true|false]

Env vars:
  POSTGRES_CONNSTR (connection string do Postgres govy_legal)
  AZURE_SEARCH_API_KEY
  AZURE_SEARCH_ENDPOINT (default: https://search-govy-kb.search.windows.net)
  OPENAI_API_KEY (se --generate-embeddings true)
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# =============================================================================
# CONFIG
# =============================================================================

AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
AZURE_SEARCH_API_KEY = os.environ.get("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "kb-legal")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

INDEX_FIELDS = {
    "chunk_id", "doc_type", "source", "tribunal", "uf", "region",
    "title", "content", "citation", "year", "authority_score", "is_current",
    "effect", "secao", "procedural_stage", "holding_outcome", "remedy_type", "claim_pattern",
    "embedding",
    "is_citable", "citable_reason", "source_work",
}

BATCH_SIZE = 50  # Chunks por batch para Azure Search

# =============================================================================
# POSTGRES
# =============================================================================

def get_postgres_conn():
    """Conecta ao Postgres govy_legal."""
    import psycopg2
    connstr = os.environ.get("POSTGRES_CONNSTR")
    if not connstr:
        raise RuntimeError("Missing POSTGRES_CONNSTR env var")
    return psycopg2.connect(connstr)


def fetch_legal_chunks(conn, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Busca chunks com metadados completos do Postgres."""
    query = """
        SELECT
            c.chunk_id,
            c.content,
            c.citation_short,
            c.hierarchy_path,
            c.char_count,
            d.doc_id,
            d.doc_type,
            d.title AS doc_title,
            d.year,
            d.jurisdiction_id,
            d.status,
            j.name AS jurisdiction_name,
            j.level AS jurisdiction_level,
            p.provision_type,
            p.label AS provision_label
        FROM legal_chunk c
        JOIN legal_document d ON c.doc_id = d.doc_id
        JOIN jurisdiction j ON d.jurisdiction_id = j.jurisdiction_id
        LEFT JOIN legal_provision p ON c.doc_id = p.doc_id AND c.provision_key = p.provision_key
        WHERE d.status = 'chunked'
        ORDER BY d.doc_id, c.order_in_doc
    """
    if limit:
        query += f" LIMIT {int(limit)}"

    with conn.cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return [dict(zip(columns, row)) for row in rows]


# =============================================================================
# MAPPING
# =============================================================================

def map_provision_type_to_secao(ptype: Optional[str]) -> str:
    """Mapeia provision_type do Postgres para secao do kb-legal."""
    if not ptype:
        return "contexto_minimo"
    ptype = ptype.lower()
    if ptype in ("artigo", "caput"):
        return "vital"
    if ptype in ("paragrafo", "inciso", "alinea"):
        return "fundamento_legal"
    if ptype in ("preambulo", "titulo", "capitulo", "secao", "anexo"):
        return "contexto_minimo"
    return "contexto_minimo"


def map_doc_type_to_effect(doc_type: str) -> str:
    """Legislacao nao tem efeito jurisprudencial — usa NAO_CLARO."""
    return "NAO_CLARO"


def build_citation(row: Dict[str, Any]) -> str:
    """Monta citacao formatada para legislacao."""
    citation_short = row.get("citation_short") or ""
    if citation_short:
        return citation_short

    doc_type = (row.get("doc_type") or "").replace("_", " ").title()
    year = row.get("year") or ""
    doc_title = row.get("doc_title") or ""
    label = row.get("provision_label") or ""

    parts = [doc_type]
    if doc_title:
        parts.append(doc_title[:100])
    if label:
        parts.append(label)
    if year:
        parts.append(f"({year})")

    return ", ".join(parts)


def build_title(row: Dict[str, Any]) -> str:
    """Monta titulo para o chunk."""
    label = row.get("provision_label") or ""
    doc_title = (row.get("doc_title") or "")[:80]
    if label and doc_title:
        return f"{label} - {doc_title}"
    return label or doc_title or row.get("chunk_id", "")


def chunk_to_kb_doc(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Converte um chunk do Postgres para documento kb-legal."""
    content = row.get("content") or ""
    if not content or len(content) < 50:
        return None

    chunk_id = row.get("chunk_id") or ""
    if not chunk_id:
        return None

    # Legislacao: prefixar chunk_id para evitar colisao com jurisprudencia
    kb_chunk_id = f"lei--{chunk_id}" if not chunk_id.startswith("lei--") else chunk_id

    year = row.get("year") or 0
    provision_type = row.get("provision_type")

    doc: Dict[str, Any] = {
        "chunk_id": kb_chunk_id,
        "doc_type": "lei",
        # Legislacao federal: sem tribunal, sem UF
        # tribunal: OMITIDO (null)
        # uf: OMITIDO (null)
        "content": content,
        "citation": build_citation(row),
        "year": int(year) if year else 0,
        "authority_score": 1.0,  # Lei = maxima autoridade
        "is_current": True,
        "secao": map_provision_type_to_secao(provision_type),
        "procedural_stage": "NAO_CLARO",
        "title": build_title(row),
        "source": f"postgres/govy_legal/{row.get('doc_id', '')}",
        "claim_pattern": f"doc_type={row.get('doc_type')};provision={provision_type or 'unknown'}",
        "effect": "NAO_CLARO",
        # Governanca: legislacao sempre citavel
        "is_citable": True,
        "citable_reason": "LEGISLACAO_VIGENTE",
        "source_work": f"legislacao_{row.get('jurisdiction_id', 'federal_br')}",
    }

    return doc


# =============================================================================
# INDEXING
# =============================================================================

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Gera embeddings em batch usando OpenAI text-embedding-3-small (ate 2048 textos por chamada)."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    # Ordenar pelo index para garantir correspondencia
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [d.embedding for d in sorted_data]


def index_batch(docs: List[Dict[str, Any]], generate_embeddings: bool) -> Dict[str, Any]:
    """Indexa um batch de docs no Azure AI Search."""
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    if not AZURE_SEARCH_API_KEY:
        return {"status": "error", "indexed": 0, "failed": len(docs), "errors": [{"error": "AZURE_SEARCH_API_KEY missing"}]}

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

    documents = []
    errors = []

    # Filtrar campos primeiro
    for doc in docs:
        filtered = {k: v for k, v in doc.items() if k in INDEX_FIELDS}
        documents.append(filtered)

    # Gerar embeddings em batch (uma unica chamada OpenAI)
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
        return {"status": "success" if failed == 0 else "partial", "indexed": indexed, "failed": failed, "errors": errors}
    except Exception as e:
        return {"status": "error", "indexed": 0, "failed": len(documents), "errors": [{"error": str(e)}]}


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="Sync legislacao do Postgres para kb-legal")
    ap.add_argument("--dry-run", action="store_true", help="Mostra docs sem indexar")
    ap.add_argument("--limit", type=int, help="Limitar numero de chunks (para teste)")
    ap.add_argument(
        "--generate-embeddings",
        default="true",
        choices=["true", "false"],
        help="Gerar embeddings OpenAI (default: true)",
    )
    args = ap.parse_args()
    generate_embeddings = args.generate_embeddings.lower() == "true"

    # 1. Conectar ao Postgres
    print("[1/4] Conectando ao Postgres govy_legal...")
    conn = get_postgres_conn()

    # 2. Buscar chunks
    print(f"[2/4] Buscando chunks (limit={args.limit or 'ALL'})...")
    rows = fetch_legal_chunks(conn, limit=args.limit)
    conn.close()
    print(f"  Encontrados: {len(rows)} chunks")

    if not rows:
        print("Nenhum chunk encontrado.")
        return

    # 3. Mapear para kb-legal
    print("[3/4] Mapeando para formato kb-legal...")
    docs = []
    skipped = 0
    doc_types = {}

    for row in rows:
        doc = chunk_to_kb_doc(row)
        if doc:
            docs.append(doc)
            dt = row.get("doc_type", "unknown")
            doc_types[dt] = doc_types.get(dt, 0) + 1
        else:
            skipped += 1

    print(f"  Mapeados: {len(docs)} docs, {skipped} pulados")
    print(f"  Por tipo: {doc_types}")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for d in docs[:3]:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        if len(docs) > 3:
            print(f"  ... +{len(docs)-3} docs")
        print(f"\nTotal: {len(docs)} docs (nao indexados)")
        return

    # 4. Indexar em batches
    print(f"[4/4] Indexando {len(docs)} docs em batches de {BATCH_SIZE} (embeddings={generate_embeddings})...")

    total_indexed = 0
    total_failed = 0
    all_errors = []

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        result = index_batch(batch, generate_embeddings)

        total_indexed += result.get("indexed", 0)
        total_failed += result.get("failed", 0)
        all_errors.extend(result.get("errors", []))

        progress = min(i + BATCH_SIZE, len(docs))
        print(f"  Batch {i//BATCH_SIZE + 1}: {result.get('indexed', 0)} indexed, {result.get('failed', 0)} failed | Progress: {progress}/{len(docs)}")

    # Relatorio
    print("\n" + "=" * 60)
    print("RELATORIO FINAL — LEGISLACAO → KB-LEGAL")
    print("=" * 60)
    print(f"Chunks Postgres:    {len(rows)}")
    print(f"Mapeados:           {len(docs)}")
    print(f"Pulados:            {skipped}")
    print(f"Indexados:          {total_indexed}")
    print(f"Falharam:           {total_failed}")
    print(f"Todos citaveis:     {len(docs)} (legislacao = sempre citavel)")
    print(f"Por doc_type:       {doc_types}")

    if all_errors:
        print(f"\nPrimeiros 5 erros:")
        for e in all_errors[:5]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
