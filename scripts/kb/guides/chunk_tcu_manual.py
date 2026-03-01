"""
GOVY - TCU Manual Semantic Chunking (hierarchical + stage_tags)
================================================================
Transforma manual_tcu_pages.json em manual_tcu.semantic_chunks.json
com hierarquia de secoes e stage_tags deterministicos.

Uso:
  python scripts/kb/guides/chunk_tcu_manual.py \
    --run-id tcu_manual_2026-02-27 \
    --date-prefix 2026-02-27 \
    [--min-chars 300] \
    [--target-chars 1200] \
    [--overlap-chars 100] \
    [--dedup true|false] \
    [--dry-run]

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ─── Config ──────────────────────────────────────────────────────────────────

STORAGE_CONTAINER = "kb-content"
DOC_ID = "tcu_manual_secom_2026_02"
DOC_TYPE = "guia_tcu"
PUBLISHER = "TCU"
SOURCE_WORK = "TCU — Licitações e Contratos: Orientações e Jurisprudência do TCU (Manual)"
INTENDED_AUDIENCE = "licitante"
USE_CASES = [
    "checklist_edital",
    "conformidade_tr",
    "riscos_licitacao",
    "boas_praticas",
]

# ─── Stage Tag Mapping (deterministic, auditable) ────────────────────────────
# Priority order: first match wins. Patterns are matched against
# section_title + breadcrumb (case-insensitive).

STAGE_TAG_RULES: List[Tuple[str, List[str]]] = [
    ("planejamento", [
        "fase preparatória", "planejamento", "etp", "estudo técnico preliminar",
        "termo de referência", "análise de riscos", "anteprojeto",
        "projeto básico", "projeto executivo", "edital",
        "audiência pública", "consulta pública", "análise jurídica",
        "pesquisa de preços", "estimativa", "orçamento",
        "plano de contratações", "pca", "pls",
        "definição do objeto", "fundamentação da contratação",
        "descrição da solução", "requisitos da contratação",
        "modelo de execução", "modelo de gestão",
        "critérios de medição", "adequação orçamentária",
        "empreitada", "contratação integrada", "contratação semi-integrada",
        "memorial descritivo", "levantamento topográfico",
        "sondagem", "método construtivo",
        "objeto da licitação", "convocação",
        "impedimento", "consórcio", "cooperativa",
        "microempresa", "pequeno porte",
        "regras da licitação", "condições contratuais",
        "matriz de riscos", "orçamento sigiloso",
        "4-1-", "4-2-", "4-3-", "4-4-", "4-5-", "4-6-", "4-7-",
    ]),
    ("edital", [
        "divulgação do edital", "impugnação", "esclarecimento",
        "apresentação de proposta", "garantia de proposta",
        "5-1-", "5-2-",
    ]),
    ("seleção", [
        "julgamento", "habilitação", "recurso", "pedido de reconsideração",
        "adjudicação", "homologação", "encerramento da licitação",
        "lance", "envio de lance",
        "aceitabilidade", "desclassificação", "desempate", "negociação",
        "garantia adicional",
        "habilitação jurídica", "habilitação técnica",
        "habilitação fiscal", "habilitação econômico",
        "infração", "sanção", "licitante",
        "procedimento auxiliar", "credenciamento", "pré-qualificação",
        "manifestação de interesse", "registro de preços", "registro cadastral",
        "contratação direta", "inexigibilidade", "dispensa",
        "fornecedor exclusivo", "artista consagrado",
        "serviços técnicos especializados", "notória especialização",
        "aquisição ou locação de imóvel",
        "formalização do contrato", "cláusula",
        "garantia", "alocação de riscos", "prerrogativa",
        "duração", "convocação para contratar", "divulgação",
        "5-3-", "5-4-", "5-5-", "5-6-", "5-7-", "5-8-",
        "5-9-", "5-10-", "5-11-",
    ]),
    ("contrato", [
        "contrato", "cláusulas", "assinatura",
        "garantias contratuais", "vigência",
    ]),
    ("gestão", [
        "gestão", "fiscalização", "recebimento", "sanções",
        "alteração", "reequilíbrio", "reajuste", "repactuação",
        "subcontratação", "execução do contrato",
        "pagamento", "meios alternativos", "resolução de controvérsias",
        "prorrogação", "extinção", "nulidade",
        "inadimplemento", "ato unilateral", "consensual",
        "decisão arbitral",
        "6-1-", "6-2-", "6-3-", "6-4-",
    ]),
    ("governança", [
        "governança", "integridade", "gestão de riscos",
        "gestão estratégica", "modelo de gestão",
        "estrutura e processos", "gestão de pessoas",
        "indicadores e metas", "logística sustentável",
        "monitoramento", "transparência", "accountability",
        "auditoria interna",
        "2-1-", "2-2-", "2-3-", "2-4-", "2-5-", "2-6-",
    ]),
]

# Fallback for chapter-level sections that don't match specific rules
CHAPTER_STAGE_MAP = {
    "1": "planejamento",  # Introdução → general context
    "2": "governança",
    "3": "planejamento",  # Metaprocesso → general context
    "4": "planejamento",
    "5": "seleção",
    "6": "gestão",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _get_conn() -> str:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage")
    return conn


def _normalize_text(text: str) -> str:
    """Normalize text for dedup: strip soft hyphens, collapse whitespace."""
    text = text.replace("\xad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def classify_stage_tag(section_title: str, breadcrumb: str, path: str) -> str:
    """Deterministic stage_tag classification based on heuristic rules."""
    search_text = f"{section_title} {breadcrumb} {path}".lower()

    for tag, patterns in STAGE_TAG_RULES:
        for pattern in patterns:
            if pattern.lower() in search_text:
                return tag

    # Fallback: use chapter number
    chapter_match = re.match(r"^(\d+)", path)
    if chapter_match:
        chapter = chapter_match.group(1)
        return CHAPTER_STAGE_MAP.get(chapter, "planejamento")

    return "planejamento"


def extract_section_id(path: str) -> str:
    """Extract a stable section ID from the URL path."""
    # Remove trailing suffixes like '-2' added by WordPress for duplicates
    clean = re.sub(r"-\d+/?$", "", path.rstrip("/"))
    return clean


def build_section_parents(section_id: str, all_sections: Dict[str, str]) -> List[Dict[str, str]]:
    """Build parent chain from section numbering.
    E.g. '4-3-2' -> parents: [{'section_id': '4', ...}, {'section_id': '4-3', ...}]
    """
    parts = section_id.split("-")
    parents = []
    for i in range(1, len(parts)):
        parent_id = "-".join(parts[:i])
        # Try to find matching section with this prefix
        parent_title = ""
        for sid, stitle in all_sections.items():
            if sid == parent_id or sid.startswith(parent_id + "-") and sid.count("-") == parent_id.count("-"):
                # Exact match
                if sid == parent_id:
                    parent_title = stitle
                    break
        parents.append({
            "section_id": parent_id,
            "title": parent_title,
        })
    return parents


def chunk_page_text(
    text: str,
    target_chars: int = 1200,
    min_chars: int = 300,
    overlap_chars: int = 100,
) -> List[str]:
    """Split text into chunks respecting paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        if not buf:
            return
        content = "\n".join(buf).strip()
        if content and len(content) >= min_chars:
            chunks.append(content)
        elif content and chunks:
            # Too short: append to previous chunk
            chunks[-1] = chunks[-1] + "\n" + content
        elif content:
            # First chunk, even if short
            chunks.append(content)
        buf = []
        buf_len = 0

    for p in paragraphs:
        p_len = len(p) + 1

        # If adding this paragraph exceeds target and we have enough content
        if buf_len + p_len > target_chars and buf_len >= min_chars:
            flush()

            # Overlap: carry last paragraph into next chunk
            if overlap_chars > 0 and chunks:
                last_chunk = chunks[-1]
                overlap_text = last_chunk[-overlap_chars:]
                # Find paragraph boundary in overlap
                nl_pos = overlap_text.find("\n")
                if nl_pos > 0:
                    overlap_text = overlap_text[nl_pos + 1:]
                if overlap_text.strip():
                    buf.append(overlap_text.strip())
                    buf_len = len(overlap_text) + 1

        buf.append(p)
        buf_len += p_len

    flush()

    return chunks


def is_toc_or_nav_page(text: str) -> bool:
    """Detect pages that are just index/TOC (mostly links, low text density)."""
    if not text or len(text) < 100:
        return True
    # Count lines vs non-empty lines
    lines = text.split("\n")
    short_lines = sum(1 for l in lines if len(l.strip()) < 30)
    if len(lines) > 5 and short_lines / len(lines) > 0.8:
        return True
    return False


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def run_chunk(
    run_id: str,
    date_prefix: str,
    input_blob: Optional[str] = None,
    output_blob: Optional[str] = None,
    min_chars: int = 300,
    target_chars: int = 1200,
    overlap_chars: int = 100,
    dedup: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute the chunking pipeline."""

    if not input_blob:
        input_blob = f"guia_tcu/raw/{date_prefix}/manual_tcu_pages.json"
    if not output_blob:
        output_blob = f"guia_tcu/processed/{date_prefix}/manual_tcu.semantic_chunks.json"

    stats = {
        "run_id": run_id,
        "date_prefix": date_prefix,
        "input_blob": input_blob,
        "output_blob": output_blob,
        "pages_processed": 0,
        "pages_skipped": 0,
        "chunks_created": 0,
        "chunks_deduped": 0,
        "stage_tag_distribution": {},
        "sections_with_title": 0,
        "sections_total": 0,
    }

    # Load pages JSON from blob
    print(f"[1/4] Loading pages from blob: {STORAGE_CONTAINER}/{input_blob}")
    from azure.storage.blob import BlobServiceClient

    conn = _get_conn()
    blob_service = BlobServiceClient.from_connection_string(conn)
    container_client = blob_service.get_container_client(STORAGE_CONTAINER)

    blob_data = container_client.get_blob_client(input_blob).download_blob().readall()
    payload = json.loads(blob_data)

    pages = payload.get("pages", [])
    print(f"  Loaded {len(pages)} pages")

    # Build section lookup for parents
    all_sections: Dict[str, str] = {}
    for page in pages:
        path = page.get("path", "")
        sid = extract_section_id(path)
        title = page.get("title", "")
        if sid:
            all_sections[sid] = title

    # Process each page into chunks
    print(f"[2/4] Chunking {len(pages)} pages (target={target_chars}, min={min_chars}, overlap={overlap_chars})...")
    all_chunks: List[Dict[str, Any]] = []
    seen_hashes: set = set()

    for page in pages:
        text = page.get("text", "")
        path = page.get("path", "")
        title = page.get("title", "")
        breadcrumb = page.get("breadcrumb", "")
        url = page.get("url", "")

        stats["sections_total"] += 1
        if title:
            stats["sections_with_title"] += 1

        # Skip TOC/navigation pages
        if is_toc_or_nav_page(text):
            stats["pages_skipped"] += 1
            continue

        # Classify stage_tag
        section_id = extract_section_id(path)
        stage_tag = classify_stage_tag(title, breadcrumb, path)

        # Build parents
        parents = build_section_parents(section_id, all_sections)

        # Chunk the text
        text_chunks = chunk_page_text(text, target_chars, min_chars, overlap_chars)

        if not text_chunks:
            stats["pages_skipped"] += 1
            continue

        stats["pages_processed"] += 1

        for chunk_idx, chunk_text in enumerate(text_chunks):
            # Deterministic chunk_id
            id_source = f"{DOC_ID}|{url}|{section_id}|{chunk_idx}"
            chunk_id = hashlib.sha256(id_source.encode()).hexdigest()[:24]
            chunk_id = f"guia_tcu--{chunk_id}"

            # Dedup by normalized text hash
            norm = _normalize_text(chunk_text)
            text_hash = _sha256(norm)

            if dedup and text_hash in seen_hashes:
                stats["chunks_deduped"] += 1
                continue
            seen_hashes.add(text_hash)

            chunk_doc: Dict[str, Any] = {
                # Doc-level
                "doc_id": DOC_ID,
                "doc_type": DOC_TYPE,
                "publisher": PUBLISHER,
                "source_work": SOURCE_WORK,
                "intended_audience": INTENDED_AUDIENCE,
                "use_case": USE_CASES,
                "is_citable": False,
                "citable_reason": "GUIA_ORIENTATIVO_NAO_NORMATIVO_USO_CHECKLIST",
                "ingest_run_id": run_id,
                # Chunk-level
                "chunk_id": chunk_id,
                "source_url": url,
                "section_id": section_id,
                "section_title": title,
                "parents": parents,
                "stage_tag": stage_tag,
                "text": chunk_text,
                "text_hash": text_hash,
                "char_count": len(chunk_text),
                "chunk_index": chunk_idx,
            }

            all_chunks.append(chunk_doc)
            stats["chunks_created"] += 1

            # Track stage_tag distribution
            stats["stage_tag_distribution"][stage_tag] = (
                stats["stage_tag_distribution"].get(stage_tag, 0) + 1
            )

    print(f"  Created {stats['chunks_created']} chunks, deduped {stats['chunks_deduped']}")

    if dry_run:
        print(f"\n=== DRY RUN ===")
        for c in all_chunks[:3]:
            preview = {k: v for k, v in c.items() if k != "text"}
            preview["text_preview"] = c["text"][:150] + "..."
            print(json.dumps(preview, ensure_ascii=False, indent=2))
        if len(all_chunks) > 3:
            print(f"  ... +{len(all_chunks)-3} chunks")
        stats["dry_run"] = True
        return stats

    # Build output JSON
    output = {
        "kind": "tcu_manual_semantic_chunks_v1",
        "run_id": run_id,
        "date_prefix": date_prefix,
        "doc_id": DOC_ID,
        "doc_type": DOC_TYPE,
        "publisher": PUBLISHER,
        "source_work": SOURCE_WORK,
        "chunk_count": len(all_chunks),
        "stage_tag_distribution": stats["stage_tag_distribution"],
        "chunks": all_chunks,
    }

    # Upload to blob
    print(f"[3/4] Uploading chunks to blob: {STORAGE_CONTAINER}/{output_blob}")
    output_json = json.dumps(output, ensure_ascii=False, indent=2)
    container_client.upload_blob(output_blob, output_json, overwrite=True)
    print(f"  Uploaded: {len(output_json):,} bytes")

    # Report
    print(f"\n[4/4] {'='*60}")
    print(f"CHUNK REPORT — TCU Manual")
    print(f"{'='*60}")
    print(f"Run ID:              {run_id}")
    print(f"Pages processed:     {stats['pages_processed']}")
    print(f"Pages skipped:       {stats['pages_skipped']}")
    print(f"Chunks created:      {stats['chunks_created']}")
    print(f"Chunks deduped:      {stats['chunks_deduped']}")
    print(f"Sections with title: {stats['sections_with_title']}/{stats['sections_total']}")
    print(f"Stage tag distribution:")
    for tag, count in sorted(stats["stage_tag_distribution"].items(), key=lambda x: -x[1]):
        pct = 100 * count / max(stats["chunks_created"], 1)
        print(f"  {tag:20s}: {count:4d} ({pct:.1f}%)")
    print(f"Output: {STORAGE_CONTAINER}/{output_blob}")

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Chunk TCU Manual (hierarchical + stage_tags)")
    ap.add_argument("--run-id", required=True, help="Unique run identifier")
    ap.add_argument("--date-prefix", required=True, help="Date prefix (e.g. 2026-02-27)")
    ap.add_argument("--input-blob", default=None,
                     help="Override input blob path (default: guia_tcu/raw/{date}/manual_tcu_pages.json)")
    ap.add_argument("--output-blob", default=None,
                     help="Override output blob path")
    ap.add_argument("--min-chars", type=int, default=300, help="Minimum chars per chunk (default: 300)")
    ap.add_argument("--target-chars", type=int, default=1200, help="Target chars per chunk (default: 1200)")
    ap.add_argument("--overlap-chars", type=int, default=100, help="Overlap chars between chunks (default: 100)")
    ap.add_argument("--dedup", default="true", choices=["true", "false"],
                     help="Deduplicate chunks by text hash (default: true)")
    ap.add_argument("--dry-run", action="store_true", help="Show chunks without uploading")
    args = ap.parse_args()

    run_chunk(
        run_id=args.run_id,
        date_prefix=args.date_prefix,
        input_blob=args.input_blob,
        output_blob=args.output_blob,
        min_chars=args.min_chars,
        target_chars=args.target_chars,
        overlap_chars=args.overlap_chars,
        dedup=args.dedup.lower() == "true",
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
