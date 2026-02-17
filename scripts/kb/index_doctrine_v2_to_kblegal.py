"""
GOVY - Doctrine v2 -> KB Legal Indexer (A1)
=============================================
Indexa semantic_chunks do doctrine_processed_v2 no indice kb-legal.

Usa diretamente index_chunks() do handler (Golden Path).
NAO passa pelo endpoint HTTP - evita problemas de envelope/formato.

Uso:
  python scripts/kb/index_doctrine_v2_to_kblegal.py \
    --processed-blob "habilitacao/habilitacao/SHA.json" \
    [--generate-embeddings true|false] \
    [--dry-run]

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
  OPENAI_API_KEY (se --generate-embeddings true)
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional


ARGUMENT_ROLE_CATALOG_V1 = {
    "DEFINICAO",
    "FINALIDADE",
    "DISTINCAO",
    "LIMITE",
    "RISCO",
    "CRITERIO",
    "PASSO_A_PASSO",
}


def _get_conn() -> str:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage")
    return conn


def _shorten(s: str, max_len: int = 80) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "..."


def map_role_to_secao(role: Optional[str]) -> str:
    """Map argument_role v1 -> secao kb-legal (lossy)."""
    if not role:
        return "contexto_minimo"
    role = role.strip().upper()
    if role in ("DEFINICAO", "FINALIDADE", "DISTINCAO"):
        return "contexto_minimo"
    if role in ("LIMITE", "RISCO"):
        return "limites"
    if role in ("CRITERIO", "PASSO_A_PASSO"):
        return "vital"
    return "contexto_minimo"


def authority_for_coverage(coverage: str) -> Optional[float]:
    """COMPLETO->0.70, PARCIAL->0.55, INCERTO->None (nao indexar)."""
    cov = (coverage or "").strip().upper()
    if cov == "COMPLETO":
        return 0.70
    if cov == "PARCIAL":
        return 0.55
    if cov == "INCERTO":
        return None
    return 0.55


def build_content(ch: Dict[str, Any]) -> str:
    """Monta content buscavel a partir dos campos do semantic_chunk."""
    pergunta = (ch.get("pergunta_ancora") or "").strip()
    tese = (ch.get("tese_neutra") or "").strip()
    explic = (ch.get("explicacao_conceitual") or "").strip()
    limites = ch.get("limites_e_cuidados") or []

    lines = []
    if pergunta:
        lines.append(f"Pergunta: {pergunta}")
        lines.append("")
    if tese:
        lines.append(f"Tese: {tese}")
        lines.append("")
    if explic:
        lines.append(f"Explicacao: {explic}")
        lines.append("")
    if limites:
        lines.append("Limites e cuidados:")
        for item in limites:
            item = (item or "").strip()
            if item:
                lines.append(f"- {item}")

    return "\n".join(lines).strip()


def make_kb_doc(
    ch: Dict[str, Any],
    processed_blob_name: str,
    internal_year: int,
) -> Optional[Dict[str, Any]]:
    """Transforma um semantic_chunk em documento kb-legal."""

    coverage = ch.get("coverage_status") or ""
    authority = authority_for_coverage(coverage)
    if authority is None:
        return None  # NAO indexar INCERTO

    chunk_id = ch.get("id")
    if not chunk_id:
        return None

    procedural_stage = (ch.get("procedural_stage") or "").strip().upper() or "NAO_CLARO"
    tema_principal = (ch.get("tema_principal") or "").strip().upper()

    role = ch.get("argument_role")
    if role is not None:
        role = str(role).strip().upper()

    secao = map_role_to_secao(role)
    pergunta = (ch.get("pergunta_ancora") or "").strip()

    # Citation com contexto (CORRECAO 3 do Claude)
    citation = f"Doutrina - {procedural_stage} - {_shorten(pergunta, 80)}"

    content = build_content(ch)
    if not content:
        return None

    # CORRECAO 1 (CRITICA): tribunal e uf OMITIDOS para doutrina
    # Omissao = null no Azure Search, evita bug REGRA #3 (uf eq null != uf eq "")
    doc: Dict[str, Any] = {
        "chunk_id": str(chunk_id).replace("::", "--"),
        "doc_type": "doutrina",
        # tribunal: OMITIDO (null) - doutrina nao e de tribunal
        # uf: OMITIDO (null) - doutrina nao tem UF
        "content": content,
        "citation": citation,
        # CORRECAO 2: year de internal_meta.ano (ano real), nao generated_at
        "year": int(internal_year) if internal_year and internal_year > 0 else 0,
        "authority_score": float(authority),
        "is_current": True,
        "secao": secao,
        "procedural_stage": procedural_stage,
        "title": pergunta or citation,
        "source": f"doutrina-processed/{processed_blob_name}",
        # Preserva metadados lossy para debug/buscas futuras
        "claim_pattern": f"argument_role={role};tema={tema_principal};coverage={coverage}",
        # Campos nao aplicaveis a doutrina - nao enviar (ficam null)
        # holding_outcome, remedy_type, effect, region: OMITIDOS
    }

    return doc


def load_processed_v2(blob_service, container: str, blob_name: str) -> Dict[str, Any]:
    """Baixa JSON doctrine_processed_v2 do Azure Blob."""
    client = blob_service.get_container_client(container)
    data = client.get_blob_client(blob_name).download_blob().readall()
    return json.loads(data)


def try_normalize(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tenta chamar normalize_chunk_for_upsert se existir (REGRA #5 KB)."""
    try:
        from govy.api.kb_index_upsert import normalize_chunk_for_upsert
        return [normalize_chunk_for_upsert(d) for d in docs]
    except ImportError:
        print("[WARN] normalize_chunk_for_upsert nao encontrado - pulando normalizacao")
        return docs
    except Exception as e:
        print(f"[WARN] normalize_chunk_for_upsert falhou: {e} - usando docs como estao")
        return docs


def main():
    ap = argparse.ArgumentParser(description="Indexa doctrine v2 semantic_chunks no kb-legal")
    ap.add_argument(
        "--processed-container",
        default=os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", "doutrina-processed"),
    )
    ap.add_argument(
        "--processed-blob",
        required=True,
        help="path completo do blob JSON v2 (ex: habilitacao/habilitacao/SHA.json)",
    )
    ap.add_argument(
        "--generate-embeddings",
        default="true",
        choices=["true", "false"],
        help="Gerar embeddings OpenAI (default: true, custo ~$0.001/chunk)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra docs que seriam indexados sem enviar ao Azure Search",
    )
    args = ap.parse_args()

    generate_embeddings = args.generate_embeddings.lower() == "true"

    # 1. Conectar ao blob
    from azure.storage.blob import BlobServiceClient
    conn = _get_conn()
    blob_service = BlobServiceClient.from_connection_string(conn)

    # 2. Baixar payload
    print(f"[1/4] Baixando {args.processed_blob}...")
    payload = load_processed_v2(blob_service, args.processed_container, args.processed_blob)

    if payload.get("kind") != "doctrine_processed_v2":
        print(f"ERRO: kind={payload.get('kind')} (esperado doctrine_processed_v2)")
        sys.exit(1)

    # 3. Extrair metadados
    internal_meta = payload.get("internal_meta") or {}
    internal_year = int(internal_meta.get("ano", 0) or 0)
    semantic_chunks = payload.get("semantic_chunks") or []

    print(f"[2/4] {len(semantic_chunks)} semantic_chunks encontrados, year={internal_year}")

    # 4. Transformar
    docs: List[Dict[str, Any]] = []
    skipped = 0
    for ch in semantic_chunks:
        doc = make_kb_doc(ch, args.processed_blob, internal_year)
        if doc:
            docs.append(doc)
        else:
            skipped += 1

    print(f"[3/4] {len(docs)} docs para indexar, {skipped} pulados (INCERTO/vazio)")

    if not docs:
        print("Nenhum doc elegivel para indexacao.")
        return

    if args.dry_run:
        print("\n=== DRY RUN - docs que seriam indexados ===")
        for d in docs:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        print(f"\n=== Total: {len(docs)} docs (nao indexados) ===")
        return

    # 5. Normalizar (REGRA #5 KB: enum clamp)
    docs = try_normalize(docs)

    # 6. Indexar via Golden Path
    print(f"[4/4] Indexando {len(docs)} docs (embeddings={generate_embeddings})...")
    from govy.api.kb_index_upsert import index_chunks

    result = index_chunks(docs, generate_embeddings=generate_embeddings)

    print("\n=== RESULTADO ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
