# govy/legal/effective_date_extractor.py
"""
Extrator de datas de publicacao e vigencia de documentos legais.

Extrai:
  - published_at: data de publicacao (DOU)
  - effective_from: inicio de vigencia ("entra em vigor na data de publicacao")
  - effective_to: fim de vigencia (se houver)
  - status_vigencia: vigente/revogada/parcialmente_revogada/desconhecido/vacatio

Se "na data de publicacao" e published_at existe → effective_from = published_at.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


@dataclass
class EffectiveDateResult:
    """Resultado da extracao de datas."""
    published_at: Optional[date]
    effective_from: Optional[date]
    effective_to: Optional[date]
    status_vigencia: str              # 'vigente', 'desconhecido', 'vacatio'
    vigor_pattern: Optional[str]      # padrao que casou para vigencia
    vigor_evidence: Optional[str]     # trecho do texto


# ── Regex patterns ────────────────────────────────────────────────────────────

# Data por extenso: "1o de abril de 2021", "23 de fevereiro de 2026"
RE_DATA_EXTENSO = re.compile(
    r"(\d{1,2})[ºo]?\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

# "publicada no DOU de DD/MM/AAAA" ou "publicada em DD.MM.AAAA"
RE_PUBLICACAO_DOU = re.compile(
    r"publicad[ao]\s+(?:no\s+(?:DOU|Di[aá]rio\s+Oficial)\s+(?:da\s+Uni[aã]o\s+)?)?(?:de|em)\s+(\d{1,2})[/\.](\d{1,2})[/\.](\d{4})",
    re.IGNORECASE,
)

# "DOU de DD de MES de AAAA"
RE_DOU_EXTENSO = re.compile(
    r"(?:DOU|Di[aá]rio\s+Oficial)\s+(?:da\s+Uni[aã]o\s+)?de\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

# Vigência: "entra em vigor na data de sua publicação"
RE_VIGOR_PUBLICACAO = re.compile(
    r"entra(?:rá)?\s+em\s+vigor\s+na\s+data\s+de\s+sua\s+publica[çc][ãa]o",
    re.IGNORECASE,
)

# Vigência: "entra em vigor após N dias"
RE_VIGOR_DIAS = re.compile(
    r"entra(?:rá)?\s+em\s+vigor\s+(?:ap[oó]s|decorridos)\s+(\d+)\s+(?:dias|dia)",
    re.IGNORECASE,
)

# Vigência: "entra em vigor em DD de MES de AAAA"
RE_VIGOR_DATA = re.compile(
    r"entra(?:rá)?\s+em\s+vigor\s+(?:em|a\s+partir\s+de)\s+(\d{1,2})[ºo]?\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

# Vigência: "produz efeitos a partir de DD/MM/AAAA"
RE_EFEITOS = re.compile(
    r"produz(?:irá|em)?\s+efeitos\s+a\s+partir\s+de\s+(\d{1,2})[/\.](\d{1,2})[/\.](\d{4})",
    re.IGNORECASE,
)

# Revogação do documento inteiro ("fica revogada esta lei/portaria/etc")
RE_REVOGADA = re.compile(
    r"fica(?:m)?\s+revogad[ao]s?\s+(?:esta|a\s+presente)",
    re.IGNORECASE,
)


def _parse_date_extenso(dia: str, mes_nome: str, ano: str) -> Optional[date]:
    """Converte data por extenso para date."""
    try:
        mes = MESES.get(mes_nome.lower())
        if not mes:
            return None
        return date(int(ano), mes, int(dia))
    except (ValueError, TypeError):
        return None


def _parse_date_numeric(dia: str, mes: str, ano: str) -> Optional[date]:
    """Converte DD/MM/AAAA para date."""
    try:
        return date(int(ano), int(mes), int(dia))
    except (ValueError, TypeError):
        return None


# ── Extração principal ────────────────────────────────────────────────────────

def extract_effective_dates(text: str, doc_id: str) -> EffectiveDateResult:
    """
    Extrai datas de publicacao e vigencia do texto.

    Args:
        text: texto completo do documento
        doc_id: para logging

    Returns:
        EffectiveDateResult
    """
    published_at = None
    effective_from = None
    effective_to = None
    status_vigencia = "desconhecido"
    vigor_pattern = None
    vigor_evidence = None

    if not text:
        return EffectiveDateResult(None, None, None, "desconhecido", None, None)

    # 1. Extrair published_at
    m = RE_PUBLICACAO_DOU.search(text)
    if m:
        published_at = _parse_date_numeric(m.group(1), m.group(2), m.group(3))

    if not published_at:
        m = RE_DOU_EXTENSO.search(text)
        if m:
            published_at = _parse_date_extenso(m.group(1), m.group(2), m.group(3))

    # 2. Extrair effective_from

    # "entra em vigor na data de sua publicação"
    m = RE_VIGOR_PUBLICACAO.search(text)
    if m:
        vigor_pattern = "RE_VIGOR_PUBLICACAO"
        start = max(0, m.start() - 20)
        vigor_evidence = text[start:m.end() + 20].strip()
        if published_at:
            effective_from = published_at
        status_vigencia = "vigente"

    # "entra em vigor após N dias"
    if not effective_from:
        m = RE_VIGOR_DIAS.search(text)
        if m:
            dias = int(m.group(1))
            vigor_pattern = "RE_VIGOR_DIAS"
            start = max(0, m.start() - 20)
            vigor_evidence = text[start:m.end() + 20].strip()
            if published_at:
                effective_from = published_at + timedelta(days=dias)
            status_vigencia = "vigente"

    # "entra em vigor em DD de MES de AAAA"
    if not effective_from:
        m = RE_VIGOR_DATA.search(text)
        if m:
            effective_from = _parse_date_extenso(m.group(1), m.group(2), m.group(3))
            vigor_pattern = "RE_VIGOR_DATA"
            start = max(0, m.start() - 20)
            vigor_evidence = text[start:m.end() + 20].strip()
            if effective_from:
                status_vigencia = "vigente"

    # "produz efeitos a partir de DD/MM/AAAA"
    if not effective_from:
        m = RE_EFEITOS.search(text)
        if m:
            effective_from = _parse_date_numeric(m.group(1), m.group(2), m.group(3))
            vigor_pattern = "RE_EFEITOS"
            start = max(0, m.start() - 20)
            vigor_evidence = text[start:m.end() + 20].strip()
            if effective_from:
                status_vigencia = "vigente"

    # 3. Tentativa de inferir ano do doc_id para published_at fallback
    if not published_at and not effective_from:
        # Tenta inferir do doc_id: lei_14133_2021_federal_br → year=2021
        m_year = re.search(r"_(\d{4})_federal", doc_id)
        if m_year:
            year = int(m_year.group(1))
            # Seta como 1 de janeiro do ano (melhor que nada)
            # NÃO setamos published_at — seria inventar dado
            # Apenas marcamos como vigente se nao temos evidence de revogacao
            pass

    logger.info(
        "doc_id=%s: published_at=%s, effective_from=%s, status=%s, pattern=%s",
        doc_id, published_at, effective_from, status_vigencia, vigor_pattern,
    )

    return EffectiveDateResult(
        published_at=published_at,
        effective_from=effective_from,
        effective_to=effective_to,
        status_vigencia=status_vigencia,
        vigor_pattern=vigor_pattern,
        vigor_evidence=vigor_evidence,
    )


# ── DB updater ────────────────────────────────────────────────────────────────

def update_document_dates(doc_id: str, dates: EffectiveDateResult):
    """Atualiza campos de vigencia no legal_document."""
    from govy.db.connection import get_conn, release_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE legal_document SET
                    published_at = %s,
                    effective_from = %s,
                    effective_to = %s,
                    status_vigencia = %s,
                    updated_at = now()
                WHERE doc_id = %s
            """, (
                dates.published_at,
                dates.effective_from,
                dates.effective_to,
                dates.status_vigencia,
                doc_id,
            ))
        conn.commit()
        logger.info("doc_id=%s: datas atualizadas", doc_id)
    except Exception:
        conn.rollback()
        logger.exception("Erro ao atualizar datas para doc_id=%s", doc_id)
        raise
    finally:
        release_conn(conn)
