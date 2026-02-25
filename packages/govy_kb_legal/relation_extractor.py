# govy/legal/relation_extractor.py
"""
Extrator de relacoes entre documentos legais (revoga, altera, regulamenta).

Regra de ouro: relacao so e "high confidence" se detectada por padrao textual
inequivoco. Caso contrario: confidence=low + needs_review=true.

Registra: padrao que casou, trecho exato (max 300 chars), posicao no documento.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

EVIDENCE_MAX_CHARS = 300


@dataclass
class RelationMatch:
    """Uma relacao detectada no texto."""
    relation_type: str          # 'revoga', 'altera', 'regulamenta', 'correlata'
    target_ref: str             # referencia textual: 'Lei 8.666/1993'
    target_doc_id: Optional[str]  # doc_id resolvido, se possivel
    confidence: str             # 'high', 'medium', 'low'
    needs_review: bool
    evidence_text: str          # trecho do texto (max 300 chars)
    evidence_pattern: str       # nome do regex que casou
    evidence_position: int      # posicao no texto
    source_provision: Optional[str] = None  # provision_key se aplicavel


# ── Patterns ──────────────────────────────────────────────────────────────────

# Tipo normativo pattern (para reutilizar)
_TIPO = r"(?:lei(?:\s+complementar)?|decreto(?:\s+legislativo)?|portaria|instru[çc][ãa]o\s+normativa|resolu[çc][ãa]o|medida\s+provis[óo]ria|emenda\s+constitucional)"
_NUM = r"n[ºo°\.\s]*\s*([\d\.]+)"
_ANO = r"(?:,?\s*de\s+\d{1,2}\s+de\s+\w+\s+de\s+)?(\d{4})"

# Revogação
RE_REVOGA_EXPLICITA = re.compile(
    rf"revoga(?:m|n?-se)?\s+(?:expressamente\s+)?(?:a|as|o|os)\s+({_TIPO})\s+{_NUM}\s*{_ANO}?",
    re.IGNORECASE,
)
RE_REVOGA_FICAM = re.compile(
    rf"ficam?\s+revogad[oa]s?\s+(?:a|as|o|os)\s+({_TIPO})\s+{_NUM}\s*{_ANO}?",
    re.IGNORECASE,
)
RE_REVOGAM_SE = re.compile(
    r"revogam-se\s+as\s+disposi[çc][õo]es\s+em\s+contr[aá]rio",
    re.IGNORECASE,
)

# Alteração
RE_ALTERA = re.compile(
    rf"altera(?:m)?\s+(?:a|as|o|os)\s+({_TIPO})\s+{_NUM}\s*{_ANO}?",
    re.IGNORECASE,
)
RE_PASSA_VIGORAR = re.compile(
    r"passa(?:m)?\s+a\s+vigorar\s+com\s+(?:a\s+)?seguinte\s+reda[çc][ãa]o",
    re.IGNORECASE,
)

# Regulamentação
RE_REGULAMENTA = re.compile(
    rf"regulamenta\s+(?:a|o)\s+({_TIPO})\s+{_NUM}\s*{_ANO}?",
    re.IGNORECASE,
)

# Referência genérica a outra norma (captura como correlata/low)
RE_REF_NORMA = re.compile(
    rf"(?:nos\s+termos\s+d[ao]|conforme|previsto\s+n[ao]|disposto\s+n[ao]|de\s+que\s+trata\s+[ao])\s+({_TIPO})\s+{_NUM}\s*{_ANO}?",
    re.IGNORECASE,
)


# ── Resolução de doc_id ──────────────────────────────────────────────────────

# Map tipo textual → prefixo curto do doc_id no DB
# DB convention: in_62_2021_federal_br (short prefix), NAO instrucao_normativa_62_...
_TYPE_MAP = {
    "lei": "lei",
    "lei complementar": "lc",
    "decreto": "decreto",
    "decreto legislativo": "decreto_legislativo",
    "portaria": "portaria",
    "instrução normativa": "in",
    "instrucao normativa": "in",
    "resolução": "resolucao",
    "resolucao": "resolucao",
    "medida provisória": "medida_provisoria",
    "medida provisoria": "medida_provisoria",
    "emenda constitucional": "emenda_constitucional",
}


def _resolve_doc_id(tipo: str, numero: str, ano: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Tenta resolver referencia em doc_id padrao.

    Returns:
        (doc_id_or_none, ref_text)
    """
    tipo_lower = tipo.strip().lower()
    tipo_key = _TYPE_MAP.get(tipo_lower, tipo_lower.replace(" ", "_"))
    num_clean = numero.replace(".", "").strip().lstrip("0") or "0"
    ref_parts = [tipo.strip(), numero.strip()]

    if ano:
        ref_parts.append(f"/{ano.strip()}")
        doc_id = f"{tipo_key}_{num_clean}_{ano.strip()}_federal_br"
    else:
        doc_id = None  # sem ano, nao da pra resolver com certeza

    ref_text = " ".join(ref_parts)
    return doc_id, ref_text


def _extract_context(text: str, pos: int, max_chars: int = EVIDENCE_MAX_CHARS) -> str:
    """Extrai trecho de contexto ao redor da posicao."""
    start = max(0, pos - 50)
    end = min(len(text), pos + max_chars - 50)
    return text[start:end].strip()


# ── Extração principal ────────────────────────────────────────────────────────

def extract_relations(text: str, doc_id: str) -> List[RelationMatch]:
    """
    Extrai relacoes do texto de um documento legal.

    Args:
        text: texto completo do documento
        doc_id: doc_id do documento fonte

    Returns:
        lista de RelationMatch
    """
    if not text:
        return []

    relations: List[RelationMatch] = []
    seen = set()  # dedup: (relation_type, target_ref)

    # ── Revogação explícita ──
    for m in RE_REVOGA_EXPLICITA.finditer(text):
        tipo, numero, ano = m.group(1), m.group(2), m.group(3)
        target_id, ref_text = _resolve_doc_id(tipo, numero, ano)
        key = ("revoga", ref_text)
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="revoga",
            target_ref=ref_text,
            target_doc_id=target_id,
            confidence="high",
            needs_review=False,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_REVOGA_EXPLICITA",
            evidence_position=m.start(),
        ))

    for m in RE_REVOGA_FICAM.finditer(text):
        tipo, numero, ano = m.group(1), m.group(2), m.group(3)
        target_id, ref_text = _resolve_doc_id(tipo, numero, ano)
        key = ("revoga", ref_text)
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="revoga",
            target_ref=ref_text,
            target_doc_id=target_id,
            confidence="high",
            needs_review=False,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_REVOGA_FICAM",
            evidence_position=m.start(),
        ))

    # "Revogam-se as disposições em contrário" — genérico, low confidence
    for m in RE_REVOGAM_SE.finditer(text):
        key = ("revoga", "disposicoes_em_contrario")
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="revoga",
            target_ref="disposicoes em contrario (generico)",
            target_doc_id=None,
            confidence="low",
            needs_review=True,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_REVOGAM_SE",
            evidence_position=m.start(),
        ))

    # ── Alteração ──
    for m in RE_ALTERA.finditer(text):
        tipo, numero, ano = m.group(1), m.group(2), m.group(3)
        target_id, ref_text = _resolve_doc_id(tipo, numero, ano)
        key = ("altera", ref_text)
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="altera",
            target_ref=ref_text,
            target_doc_id=target_id,
            confidence="high",
            needs_review=False,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_ALTERA",
            evidence_position=m.start(),
        ))

    # ── Regulamentação ──
    for m in RE_REGULAMENTA.finditer(text):
        tipo, numero, ano = m.group(1), m.group(2), m.group(3)
        target_id, ref_text = _resolve_doc_id(tipo, numero, ano)
        key = ("regulamenta", ref_text)
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="regulamenta",
            target_ref=ref_text,
            target_doc_id=target_id,
            confidence="high",
            needs_review=False,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_REGULAMENTA",
            evidence_position=m.start(),
        ))

    # ── Referências genéricas (correlata, low) ──
    for m in RE_REF_NORMA.finditer(text):
        tipo, numero, ano = m.group(1), m.group(2), m.group(3)
        target_id, ref_text = _resolve_doc_id(tipo, numero, ano)
        key = ("referencia", ref_text)
        if key in seen:
            continue
        seen.add(key)
        relations.append(RelationMatch(
            relation_type="referencia",
            target_ref=ref_text,
            target_doc_id=target_id,
            confidence="low",
            needs_review=True,
            evidence_text=_extract_context(text, m.start()),
            evidence_pattern="RE_REF_NORMA",
            evidence_position=m.start(),
        ))

    logger.info(
        "doc_id=%s: %d relacoes detectadas (high=%d, low=%d)",
        doc_id, len(relations),
        sum(1 for r in relations if r.confidence == "high"),
        sum(1 for r in relations if r.confidence == "low"),
    )
    return relations


# ── DB helpers ────────────────────────────────────────────────────────────────

def _resolve_target_in_db(cur, target_doc_id: Optional[str]) -> Optional[str]:
    """
    Tenta resolver target_doc_id no DB, incluindo variantes de numero.

    DB doc_ids podem ter leading zeros inconsistentes:
      in_01_2010 vs in_5_2017
    Tentamos: exact → com zero → sem zero.
    """
    if not target_doc_id:
        return None

    # 1. Exact match
    cur.execute("SELECT doc_id FROM legal_document WHERE doc_id = %s", (target_doc_id,))
    row = cur.fetchone()
    if row:
        return row[0]

    # 2. Try with leading zero on number (e.g. in_2_2010 → in_02_2010)
    import re as _re
    m = _re.match(r"^([a-z_]+)_(\d+)_(\d{4})_(.+)$", target_doc_id)
    if m:
        prefix, num, ano, suffix = m.groups()
        # Try with zero-padded number
        if len(num) == 1:
            alt = f"{prefix}_{num.zfill(2)}_{ano}_{suffix}"
            cur.execute("SELECT doc_id FROM legal_document WHERE doc_id = %s", (alt,))
            row = cur.fetchone()
            if row:
                return row[0]
        # Try without leading zeros
        num_stripped = num.lstrip("0") or "0"
        if num_stripped != num:
            alt = f"{prefix}_{num_stripped}_{ano}_{suffix}"
            cur.execute("SELECT doc_id FROM legal_document WHERE doc_id = %s", (alt,))
            row = cur.fetchone()
            if row:
                return row[0]

    return None


# ── DB writer ─────────────────────────────────────────────────────────────────

def write_relations(doc_id: str, relations: List[RelationMatch]):
    """Grava relacoes no Postgres. Idempotente (deleta existentes e re-insere)."""
    from govy.db.connection import get_conn, release_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Limpa relacoes existentes deste doc
            cur.execute("DELETE FROM legal_relation WHERE source_doc_id = %s", (doc_id,))

            for rel in relations:
                # Verifica se target_doc_id existe no DB
                resolved_target = _resolve_target_in_db(cur, rel.target_doc_id)

                cur.execute("""
                    INSERT INTO legal_relation (
                        source_doc_id, target_doc_id, target_ref,
                        relation_type, source_provision, notes,
                        confidence, needs_review,
                        evidence_text, evidence_pattern, evidence_position
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    doc_id,
                    resolved_target,
                    rel.target_ref,
                    rel.relation_type,
                    rel.source_provision,
                    None,
                    rel.confidence,
                    rel.needs_review,
                    rel.evidence_text,
                    rel.evidence_pattern,
                    rel.evidence_position,
                ))

        conn.commit()
        logger.info("doc_id=%s: %d relacoes gravadas", doc_id, len(relations))
    except Exception:
        conn.rollback()
        logger.exception("Erro ao gravar relacoes para doc_id=%s", doc_id)
        raise
    finally:
        release_conn(conn)
