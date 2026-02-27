"""
GOVY - Doctrine v2 -> KB Legal Indexer (A2 - Governance + OCR Gate)
====================================================================
Indexa semantic_chunks (e opcionalmente raw_chunks como fallback)
do doctrine_processed_v2 no indice kb-legal.

Respeita configs/doctrine_policy.json para governanca de citabilidade.
Inclui OCR quality gate para raw_chunks (check_gibberish_quality).

Usa diretamente index_chunks() do handler (Golden Path).
NAO passa pelo endpoint HTTP - evita problemas de envelope/formato.

Uso:
  # Indexar um blob especifico:
  python scripts/kb/index_doctrine_v2_to_kblegal.py \
    --processed-blob "licitacao/licitacao/SHA.json" \
    [--generate-embeddings true|false] \
    [--dry-run]

  # Indexar TODOS os blobs do container (batch):
  python scripts/kb/index_doctrine_v2_to_kblegal.py \
    --batch \
    [--generate-embeddings true|false] \
    [--dry-run]

  # Indexar usando raw_chunks como fallback:
  python scripts/kb/index_doctrine_v2_to_kblegal.py \
    --batch --use-raw-fallback \
    [--dry-run]

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
  AZURE_SEARCH_API_KEY
  OPENAI_API_KEY (se --generate-embeddings true)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# CONSTANTES
# =============================================================================

ARGUMENT_ROLE_CATALOG_V1 = {
    "DEFINICAO",
    "FINALIDADE",
    "DISTINCAO",
    "LIMITE",
    "RISCO",
    "CRITERIO",
    "PASSO_A_PASSO",
}

DEFAULT_PROCESSED_CONTAINER = "kb-doutrina-processed"
POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "configs" / "doctrine_policy.json"

# Stopwords pt-BR mínimas para detecção de gibberish (texto jurídico)
_STOPWORDS_PTBR = frozenset({
    "a", "à", "ao", "aos", "as", "às", "até",
    "com", "como", "contra",
    "da", "das", "de", "do", "dos", "e", "em", "entre", "é",
    "foi", "for", "foram",
    "na", "nas", "no", "nos", "não", "nem",
    "o", "os", "ou",
    "para", "pela", "pelas", "pelo", "pelos", "por",
    "que", "qual", "quando",
    "se", "sem", "ser", "seu", "sua", "são",
    "um", "uma",
    # Termos jurídicos frequentes
    "art", "lei", "contrato", "contratos", "licitação", "licitações",
    "deve", "pode", "será", "sobre", "caso", "forma", "prazo",
    "público", "pública", "públicos", "públicas",
    "administração", "contratação", "edital",
})


# =============================================================================
# HELPERS
# =============================================================================

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


def load_doctrine_policy() -> Dict[str, Any]:
    """Carrega doctrine_policy.json. Retorna {} se nao existir."""
    if POLICY_PATH.exists():
        with open(POLICY_PATH, encoding="utf-8") as f:
            return json.load(f)
    print(f"[WARN] Policy nao encontrada em {POLICY_PATH} - usando defaults")
    return {}


def identify_work(source_blob_name: str) -> str:
    """Extrai o identificador da obra a partir do blob_name da fonte raw."""
    # source.blob_name format: "marcal/comentarios_a_lei_.../.../doc_metadata.json"
    if "/" in source_blob_name:
        return source_blob_name.split("/")[0]
    return "unknown"


def get_work_policy(policy: Dict, work_key: str) -> Dict[str, Any]:
    """Retorna policy da obra. Default: KNOWLEDGE_ONLY, nao citavel."""
    works = policy.get("works", {})
    return works.get(work_key, {
        "can_cite_in_defense": False,
        "can_cite_in_chat": False,
        "quality_notes": "Obra sem policy definida - default KNOWLEDGE_ONLY",
    })


def check_chunk_quality(content: str, policy: Dict) -> Tuple[bool, str]:
    """
    Avalia qualidade do chunk para citabilidade.
    Retorna (is_citable, citable_reason).
    """
    gates = policy.get("chunk_quality_gates", {})
    min_chars = gates.get("min_content_chars", 200)
    min_alpha = gates.get("min_alpha_ratio", 0.7)

    if not content or len(content) < min_chars:
        return False, "FRAGMENTADO"

    alpha_count = sum(1 for c in content if c.isalpha())
    total = len(content)
    if total > 0 and (alpha_count / total) < min_alpha:
        return False, "OCR_RUIDOSO"

    return True, "OK"


def check_gibberish_quality(text: str, min_chars: int = 600) -> Tuple[bool, str, Dict[str, float]]:
    """
    OCR quality gate para raw_chunks.
    Detecta gibberish textual (palavras sem sentido de OCR ruim).

    Retorna (passed, reject_reason, metrics).
    Se passed=True, reject_reason="" e metrics contém os valores calculados.

    Calibrado com dados reais pt-BR jurídico (2026-02-27):
    - Texto limpo: single_char ~0.07-0.11, short_token ~0.28-0.35,
      stopword ~0.37-0.45, vowel ~0.47-0.50
    - Gibberish OCR: single_char ~0.13-0.18, short_token ~0.33-0.39,
      stopword ~0.33-0.37
    """
    metrics: Dict[str, float] = {}

    if not text or len(text) < min_chars:
        return False, "TOO_SHORT", {"len": len(text) if text else 0}

    # Normalizar: remover soft-hyphen
    clean = text.replace("\xad", "")

    # Tokenizar por espaço, strip de pontuação nas bordas
    raw_tokens = clean.split()
    tokens = []
    for t in raw_tokens:
        t = re.sub(r'^[.,;:!?()\[\]{}\'"«»\u201c\u201d\u2014\u2013\-]+', '', t)
        t = re.sub(r'[.,;:!?()\[\]{}\'"«»\u201c\u201d\u2014\u2013\-]+$', '', t)
        if t:
            tokens.append(t)

    if len(tokens) < 10:
        return False, "TOO_FEW_TOKENS", {"token_count": len(tokens)}

    n = len(tokens)
    alpha_tokens = [t for t in tokens if t.isalpha()]
    n_alpha = len(alpha_tokens)

    # 1. single_char_rate
    single_char = sum(1 for t in tokens if len(t) == 1)
    single_char_rate = single_char / n
    metrics["single_char_rate"] = round(single_char_rate, 4)

    # 2. short_token_rate (len <= 2)
    short_tokens = sum(1 for t in tokens if len(t) <= 2)
    short_token_rate = short_tokens / n
    metrics["short_token_rate"] = round(short_token_rate, 4)

    # 3. digit_token_rate (informational, not gated)
    digit_tokens = sum(1 for t in tokens if t.isdigit())
    digit_token_rate = digit_tokens / n
    metrics["digit_token_rate"] = round(digit_token_rate, 4)

    # 4. avg_token_len (tokens alfabéticos)
    if n_alpha > 0:
        avg_token_len = sum(len(t) for t in alpha_tokens) / n_alpha
    else:
        avg_token_len = 0.0
    metrics["avg_token_len"] = round(avg_token_len, 2)

    # 5. vowel_ratio (em tokens alfabéticos)
    vowels = set("aeiouáàâãéêíóôõúç")
    if n_alpha > 0:
        alpha_chars = "".join(alpha_tokens).lower()
        vowel_count = sum(1 for c in alpha_chars if c in vowels)
        vowel_ratio = vowel_count / len(alpha_chars) if alpha_chars else 0.0
    else:
        vowel_ratio = 0.0
    metrics["vowel_ratio"] = round(vowel_ratio, 4)

    # 6. stopword_hit_rate
    tokens_lower = [t.lower() for t in tokens]
    stopword_hits = sum(1 for t in tokens_lower if t in _STOPWORDS_PTBR)
    stopword_hit_rate = stopword_hits / n
    metrics["stopword_hit_rate"] = round(stopword_hit_rate, 4)

    # --- GATES ---

    # Gate 1: gibberish pesado (chars soltos demais)
    if single_char_rate > 0.16:
        return False, "HIGH_SINGLE_CHAR_RATE", metrics

    # Gate 2: texto sem estrutura linguística (poucas stopwords pt-BR)
    if stopword_hit_rate < 0.25:
        return False, "LOW_STOPWORD_HIT_RATE", metrics

    # Gate 3: tokens sem vogais (gibberish consonantal)
    if vowel_ratio < 0.33:
        return False, "LOW_VOWEL_RATIO", metrics

    # Gate 4: combinação single_char + short_token alta = gibberish moderado
    # Texto limpo: single ~0.09 + short ~0.30 = ~0.39
    # Garbage: single ~0.15 + short ~0.36 = ~0.51
    noise_score = single_char_rate + short_token_rate
    metrics["noise_score"] = round(noise_score, 4)
    if noise_score > 0.46:
        return False, "HIGH_NOISE_SCORE", metrics

    return True, "", metrics


# =============================================================================
# MAPPERS
# =============================================================================

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


def build_content_from_semantic(ch: Dict[str, Any]) -> str:
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


def build_content_from_raw(ch: Dict[str, Any]) -> str:
    """Extrai content de raw_chunk."""
    return (ch.get("content_raw") or "").strip()


# =============================================================================
# DOC BUILDERS
# =============================================================================

def make_kb_doc_from_semantic(
    ch: Dict[str, Any],
    processed_blob_name: str,
    internal_year: int,
    work_key: str,
    work_policy: Dict,
    global_policy: Dict,
) -> Optional[Dict[str, Any]]:
    """Transforma um semantic_chunk em documento kb-legal com governanca."""

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

    citation = f"Doutrina - {procedural_stage} - {_shorten(pergunta, 80)}"

    content = build_content_from_semantic(ch)
    if not content:
        return None

    # Governanca de citabilidade
    can_cite = work_policy.get("can_cite_in_defense", False)
    if can_cite:
        is_citable, citable_reason = check_chunk_quality(content, global_policy)
    else:
        is_citable = False
        citable_reason = "OBRA_NAO_CITAVEL"

    doc: Dict[str, Any] = {
        "chunk_id": str(chunk_id).replace("::", "--"),
        "doc_type": "doutrina",
        "content": content,
        "citation": citation,
        "year": int(internal_year) if internal_year and internal_year > 0 else 0,
        "authority_score": float(authority),
        "is_current": True,
        "secao": secao,
        "procedural_stage": procedural_stage,
        "title": pergunta or citation,
        "source": f"doutrina-processed/{processed_blob_name}",
        "claim_pattern": f"argument_role={role};tema={tema_principal};coverage={coverage}",
        # Governanca (v1)
        "is_citable": is_citable,
        "citable_reason": citable_reason,
        "source_work": work_key,
    }

    return doc


def make_kb_doc_from_raw(
    ch: Dict[str, Any],
    processed_blob_name: str,
    internal_year: int,
    work_key: str,
    chunk_index: int,
) -> Optional[Dict[str, Any]]:
    """Transforma um raw_chunk em documento kb-legal (KNOWLEDGE_ONLY, nunca citavel)."""

    content = build_content_from_raw(ch)
    if not content or len(content) < 100:
        return None

    chunk_id = ch.get("chunk_id") or ch.get("id")
    if not chunk_id:
        # Gera ID deterministico
        source_sha = ch.get("source_sha", "unknown")
        chunk_id = f"raw--{source_sha}--{chunk_index}"

    procedural_stage = (ch.get("procedural_stage") or "").strip().upper() or "NAO_CLARO"

    doc: Dict[str, Any] = {
        "chunk_id": str(chunk_id).replace("::", "--"),
        "doc_type": "doutrina",
        "content": content,
        "citation": f"Doutrina (raw) - {work_key}",
        "year": int(internal_year) if internal_year and internal_year > 0 else 0,
        "authority_score": 0.40,  # Raw = menor autoridade
        "is_current": True,
        "secao": "contexto_minimo",
        "procedural_stage": procedural_stage,
        "title": f"Doutrina raw - {work_key} - chunk {chunk_index}",
        "source": f"doutrina-processed/{processed_blob_name}",
        "claim_pattern": f"chunk_type=raw;work={work_key}",
        # Governanca: raw NUNCA e citavel
        "is_citable": False,
        "citable_reason": "RAW_CHUNK_SEM_ENRICHMENT",
        "source_work": work_key,
    }

    return doc


# =============================================================================
# LOADERS
# =============================================================================

def load_processed_v2(blob_service, container: str, blob_name: str) -> Dict[str, Any]:
    """Baixa JSON doctrine_processed_v2 do Azure Blob."""
    client = blob_service.get_container_client(container)
    data = client.get_blob_client(blob_name).download_blob().readall()
    return json.loads(data)


def try_normalize(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tenta chamar normalize_chunk_for_upsert se existir (REGRA #5 KB)."""
    try:
        from govy.utils.juris_constants import normalize_chunk_for_upsert
        return [normalize_chunk_for_upsert(d) for d in docs]
    except ImportError:
        # Fallback: tenta via packages path
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
            from packages.govy_platform.utils.juris_constants import normalize_chunk_for_upsert
            return [normalize_chunk_for_upsert(d) for d in docs]
        except ImportError:
            print("[WARN] normalize_chunk_for_upsert nao encontrado - pulando normalizacao")
            return docs
    except Exception as e:
        print(f"[WARN] normalize_chunk_for_upsert falhou: {e} - usando docs como estao")
        return docs


# =============================================================================
# INDEX DIRECT (sem depender de azure.functions)
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


def _generate_embedding(text: str) -> List[float]:
    """Gera embedding usando OpenAI text-embedding-3-small."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def _index_chunks_direct(chunks: List[Dict], generate_embeddings: bool = True) -> Dict[str, Any]:
    """Indexa chunks diretamente via Azure Search SDK (sem depender de azure.functions)."""
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    if not AZURE_SEARCH_API_KEY:
        return {"status": "error", "indexed": 0, "failed": len(chunks), "errors": [{"error": "AZURE_SEARCH_API_KEY nao configurada"}]}

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

    documents = []
    errors = []

    for i, chunk in enumerate(chunks):
        try:
            # Filtra apenas campos do indice
            doc = {k: v for k, v in chunk.items() if k in INDEX_FIELDS}
            if generate_embeddings and doc.get("content"):
                doc["embedding"] = _generate_embedding(doc["content"])
            documents.append(doc)
        except Exception as e:
            errors.append({"index": i, "chunk_id": chunk.get("chunk_id"), "error": str(e)})

    if not documents:
        return {"status": "error", "indexed": 0, "failed": len(chunks), "errors": errors}

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
# PROCESS ONE BLOB
# =============================================================================

def process_blob(
    blob_service,
    container: str,
    blob_name: str,
    policy: Dict,
    use_raw_fallback: bool,
    generate_embeddings: bool,
    dry_run: bool,
) -> Dict[str, int]:
    """Processa um blob e retorna contadores."""
    payload = load_processed_v2(blob_service, container, blob_name)

    if payload.get("kind") != "doctrine_processed_v2":
        print(f"  SKIP: kind={payload.get('kind')} (esperado doctrine_processed_v2)")
        return {"skipped_wrong_kind": 1}

    # Identificar obra
    source = payload.get("source") or {}
    raw_blob_name = source.get("blob_name", "")
    work_key = identify_work(raw_blob_name)
    work_pol = get_work_policy(policy, work_key)

    internal_meta = payload.get("internal_meta") or {}
    internal_year = int(internal_meta.get("ano", 0) or 0)

    semantic_chunks = payload.get("semantic_chunks") or []
    raw_chunks = payload.get("raw_chunks") or []

    docs: List[Dict[str, Any]] = []
    skipped = 0
    used_raw = False

    # Preferir semantic_chunks
    if semantic_chunks:
        for ch in semantic_chunks:
            doc = make_kb_doc_from_semantic(
                ch, blob_name, internal_year, work_key, work_pol, policy
            )
            if doc:
                docs.append(doc)
            else:
                skipped += 1
    elif use_raw_fallback and raw_chunks:
        # Fallback: usar raw_chunks (KNOWLEDGE_ONLY) com OCR quality gate
        used_raw = True
        raw_accepted = 0
        raw_rejected = 0
        raw_reject_reasons: Dict[str, int] = {}
        for i, ch in enumerate(raw_chunks):
            content = build_content_from_raw(ch)
            passed, reason, metrics = check_gibberish_quality(content)
            if not passed:
                raw_rejected += 1
                raw_reject_reasons[reason] = raw_reject_reasons.get(reason, 0) + 1
                skipped += 1
                continue
            doc = make_kb_doc_from_raw(ch, blob_name, internal_year, work_key, i)
            if doc:
                docs.append(doc)
                raw_accepted += 1
            else:
                skipped += 1

    # Contadores de raw fallback (só existem se usou raw)
    _raw_accepted = raw_accepted if used_raw else 0
    _raw_rejected = raw_rejected if used_raw else 0
    _raw_reject_reasons = raw_reject_reasons if used_raw else {}

    # Blob-level gate: exigir volume minimo de texto aceito
    if used_raw and docs:
        accepted_chars = sum(len(d.get("content", "")) for d in docs)
        total_raw = len(raw_chunks)
        # Gate 1: minimo 1200 chars aceitos no blob
        if accepted_chars < 1200:
            docs = []
            _raw_reject_reasons["BLOB_LOW_CHARS"] = _raw_reject_reasons.get("BLOB_LOW_CHARS", 0) + 1
        # Gate 2: se blob grande (>40 chunks), exigir >= 20% aceitos
        elif total_raw > 40 and _raw_accepted / total_raw < 0.20:
            docs = []
            _raw_reject_reasons["BLOB_LOW_RATIO"] = _raw_reject_reasons.get("BLOB_LOW_RATIO", 0) + 1

    if not docs:
        result_base = {"empty": 1, "skipped": skipped, "work": work_key}
        if used_raw:
            result_base["raw_accepted"] = _raw_accepted
            result_base["raw_rejected"] = _raw_rejected
            result_base["raw_reject_reasons"] = _raw_reject_reasons
        return result_base

    citable_count = sum(1 for d in docs if d.get("is_citable"))

    if dry_run:
        for d in docs[:2]:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        if len(docs) > 2:
            print(f"  ... +{len(docs)-2} docs")
        result_dry = {"dry_run_docs": len(docs), "skipped": skipped, "work": work_key, "is_citable_count": citable_count}
        if used_raw:
            result_dry["raw_accepted"] = _raw_accepted
            result_dry["raw_rejected"] = _raw_rejected
            result_dry["raw_reject_reasons"] = _raw_reject_reasons
        return result_dry

    # Normalizar
    docs = try_normalize(docs)

    # Indexar diretamente via Azure Search SDK
    result = _index_chunks_direct(docs, generate_embeddings=generate_embeddings)

    indexed = result.get("indexed", 0)
    failed = result.get("failed", 0)
    errors = result.get("errors", [])

    if errors:
        print(f"  ERRORS in {blob_name}: {errors[:2]}")

    result_live = {
        "indexed": indexed,
        "failed": failed,
        "skipped": skipped,
        "used_raw": 1 if used_raw else 0,
        "work": work_key,
        "is_citable_count": citable_count,
        "errors": errors,
    }
    if used_raw:
        result_live["raw_accepted"] = _raw_accepted
        result_live["raw_rejected"] = _raw_rejected
        result_live["raw_reject_reasons"] = _raw_reject_reasons
    return result_live


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="Indexa doctrine v2 no kb-legal com governanca")
    ap.add_argument(
        "--processed-container",
        default=os.getenv("DOCTRINE_PROCESSED_CONTAINER_NAME", DEFAULT_PROCESSED_CONTAINER),
    )
    ap.add_argument(
        "--processed-blob",
        help="path de um blob especifico (ex: licitacao/licitacao/SHA.json)",
    )
    ap.add_argument(
        "--batch",
        action="store_true",
        help="Processar TODOS os blobs do container",
    )
    ap.add_argument(
        "--use-raw-fallback",
        action="store_true",
        help="Indexar raw_chunks se semantic_chunks nao existirem (KNOWLEDGE_ONLY)",
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

    if not args.batch and not args.processed_blob:
        ap.error("Precisa de --processed-blob ou --batch")

    generate_embeddings = args.generate_embeddings.lower() == "true"

    # 1. Carregar policy
    policy = load_doctrine_policy()
    works_config = policy.get("works", {})
    print(f"[CONFIG] Policy: {len(works_config)} obras configuradas")
    for wk, wp in works_config.items():
        cite = "CITABLE" if wp.get("can_cite_in_defense") else "KNOWLEDGE_ONLY"
        print(f"  {wk}: {cite}")

    # 2. Conectar ao blob
    from azure.storage.blob import BlobServiceClient
    conn = _get_conn()
    blob_service = BlobServiceClient.from_connection_string(conn)

    # 3. Listar blobs
    if args.batch:
        cc = blob_service.get_container_client(args.processed_container)
        blob_names = [b.name for b in cc.list_blobs()]
        print(f"\n[BATCH] {len(blob_names)} blobs no container {args.processed_container}")
    else:
        blob_names = [args.processed_blob]

    # 4. Processar
    totals = {
        "processed": 0,
        "indexed": 0,
        "failed": 0,
        "skipped": 0,
        "empty": 0,
        "used_raw": 0,
        "is_citable": 0,
        "raw_accepted": 0,
        "raw_rejected": 0,
    }
    per_work: Dict[str, Dict[str, int]] = {}
    all_errors = []
    all_raw_reject_reasons: Dict[str, int] = {}

    for i, bn in enumerate(blob_names):
        if args.batch and (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(blob_names)}")

        result = process_blob(
            blob_service, args.processed_container, bn,
            policy, args.use_raw_fallback, generate_embeddings, args.dry_run,
        )

        totals["processed"] += 1
        totals["indexed"] += result.get("indexed", 0) + result.get("dry_run_docs", 0)
        totals["failed"] += result.get("failed", 0)
        totals["skipped"] += result.get("skipped", 0)
        totals["empty"] += result.get("empty", 0)
        totals["used_raw"] += result.get("used_raw", 0)
        totals["is_citable"] += result.get("is_citable_count", 0)
        totals["raw_accepted"] += result.get("raw_accepted", 0)
        totals["raw_rejected"] += result.get("raw_rejected", 0)
        for reason, cnt in result.get("raw_reject_reasons", {}).items():
            all_raw_reject_reasons[reason] = all_raw_reject_reasons.get(reason, 0) + cnt
        all_errors.extend(result.get("errors", []))

        work = result.get("work", "unknown")
        if work not in per_work:
            per_work[work] = {"indexed": 0, "citable": 0}
        per_work[work]["indexed"] += result.get("indexed", 0) + result.get("dry_run_docs", 0)
        per_work[work]["citable"] += result.get("is_citable_count", 0)

    # 5. Relatorio
    print("\n" + "=" * 60)
    print("RELATORIO FINAL")
    print("=" * 60)
    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"Modo: {mode}")
    print(f"Blobs processados: {totals['processed']}")
    print(f"Chunks indexados:  {totals['indexed']}")
    print(f"Chunks falharam:   {totals['failed']}")
    print(f"Chunks pulados:    {totals['skipped']}")
    print(f"Blobs vazios:      {totals['empty']}")
    print(f"Usaram raw_chunks: {totals['used_raw']}")
    print(f"Chunks citaveis:   {totals['is_citable']}")
    if totals["raw_accepted"] > 0 or totals["raw_rejected"] > 0:
        print()
        print("Raw fallback (OCR quality gate):")
        print(f"  raw_accepted:  {totals['raw_accepted']}")
        print(f"  raw_rejected:  {totals['raw_rejected']}")
        if all_raw_reject_reasons:
            print("  reject_reasons:")
            for reason, cnt in sorted(all_raw_reject_reasons.items(), key=lambda x: -x[1]):
                print(f"    {reason}: {cnt}")
    print()
    print("Por obra:")
    for wk, wd in sorted(per_work.items()):
        print(f"  {wk}: {wd['indexed']} indexed, {wd['citable']} citable")

    # Mostrar primeiros erros se houver
    if all_errors:
        print(f"\nPrimeiros 5 erros:")
        for e in all_errors[:5]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
