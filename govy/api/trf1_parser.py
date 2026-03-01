"""
trf1_parser.py
Parser dedicado para TRF1 (Tribunal Regional Federal da 1ª Região).

TRF1 usa dados coletados via CJF unified portal (scraper_cjf_http.py).
Somente metadata + ementa curta (avg 86 chars) — sem inteiro teor.
Inteiro teor em pje2g.trf1.jus.br (reCAPTCHA) e arquivo.trf1.jus.br (Cloudflare).

Campos JSON do scraper CJF: cjf_doc_id, tribunal_search, tipo, processo,
numero_raw, classe, relator, origem, data_decisao, data_publicacao,
fonte_publicacao, ementa, inteiro_teor_url, inteiro_teor_text, doc_id,
relator_convocado (opcional), scraped_at.

Produz output compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

Inclui exclusao GOVY: itens com 'crime' ou 'criminal' sao rejeitados (terminal_excluded).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from govy.api.tce_parser_v3 import (
    MISSING,
    classify_outcome_effect_from_dispositivo,
    classify_procedural_stage,
    detect_claim_patterns,
    extract_references,
    is_current_from_year,
    normalize_text,
)

# GOVY exclusion patterns (NÃO crime NÃO criminal)
_EXCLUSION_RE = re.compile(r"\bcrime\b|\bcriminal\b", re.IGNORECASE)


def _safe_str(val: Any) -> str:
    """Retorna string limpa ou MISSING."""
    if val is None:
        return MISSING
    s = str(val).strip()
    return s if s else MISSING


def _safe_text(val: Any) -> str:
    """Retorna texto normalizado ou MISSING."""
    if val is None:
        return MISSING
    s = normalize_text(str(val))
    return s if len(s) >= 5 else MISSING


def _format_date_cjf(raw_date: Any) -> str:
    """
    Converte data CJF (formato 'DD/MM/YYYY') para 'DD/MM/YYYY'.
    Aceita tambem ISO 'YYYY-MM-DD'.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    # Already DD/MM/YYYY
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    # ISO format
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento a partir de data_decisao ou data_publicacao."""
    for field in ("data_decisao", "data_publicacao"):
        date_val = data.get(field)
        if date_val:
            m = re.search(r"(\d{4})", str(date_val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    return MISSING


def _infer_classe_tipo(classe: str) -> str:
    """Infere tipo de processo a partir da classe judicial."""
    if classe == MISSING:
        return "Acordao"
    c = classe.upper()
    if "AGRAVO" in c or "RECURSO" in c:
        return "Recurso"
    if "EMBARGOS" in c:
        return "Embargos"
    if "MANDADO" in c:
        return "Mandado de Seguranca"
    return "Acordao"


def parse_trf1_cjf_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TRF1 (CJF metadata blob) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper_cjf_http.py)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se ementa vazia (terminal_no_text) ou excluido
        por filtro GOVY crime/criminal (terminal_excluded).
    """
    # --- Check terminal_no_text ---
    ementa_raw = data.get("ementa")
    if not ementa_raw or not str(ementa_raw).strip():
        return None

    # --- GOVY exclusion: crime/criminal ---
    if _EXCLUSION_RE.search(str(ementa_raw)):
        return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("processo"))
    classe = _safe_str(data.get("classe"))
    relator = _safe_str(data.get("relator"))
    # Some docs have relator_convocado
    if relator == MISSING:
        relator = _safe_str(data.get("relator_convocado"))
    orgao_julgador = _safe_str(data.get("origem"))

    # --- Texto ---
    ementa = _safe_text(ementa_raw)
    # TRF1 CJF data has no full text — ementa is all we have
    dispositivo = ementa  # use ementa as dispositivo

    # --- Acordao numero (from CJF doc_id or processo) ---
    cjf_doc_id = _safe_str(data.get("cjf_doc_id"))
    acordao_numero = processo if processo != MISSING else cjf_doc_id

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)

    claim_patterns = detect_claim_patterns(ementa) if ementa != MISSING else []

    holding_outcome, effect = classify_outcome_effect_from_dispositivo(ementa)

    # --- Datas ---
    julgamento_date = _format_date_cjf(data.get("data_decisao"))
    pub_date = _format_date_cjf(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References ---
    refs = extract_references(ementa) if ementa != MISSING else []

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TRF",
        "tribunal_name": "TRIBUNAL REGIONAL FEDERAL DA 1ª REGIÃO",
        "uf": None,
        "region": MISSING,
        "processo": processo,
        "acordao_numero": acordao_numero,
        "relator": relator,
        "orgao_julgador": orgao_julgador,
        "ementa": ementa,
        "dispositivo": dispositivo,
        "holding_outcome": holding_outcome,
        "effect": effect,
        "publication_number": MISSING,
        "publication_date": pub_date,
        "julgamento_date": julgamento_date,
        "references": refs,
        "linked_processes": refs,
        "procedural_stage": stage,
        "claim_pattern": claim_patterns,
        "authority_score": "0.85",
        "year": year,
        "is_current": current,
        "key_citation": ementa if ementa != MISSING else MISSING,
        "key_citation_speaker": "TRIBUNAL" if ementa != MISSING else MISSING,
        "key_citation_source": "EMENTA_CJF" if ementa != MISSING else MISSING,
    }

    return out
