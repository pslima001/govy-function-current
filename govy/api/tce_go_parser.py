"""
tce_go_parser.py
Parser dedicado para TCE-GO (Goias).

TCE-GO usa API REST Iago com texto inline completo no campo `full_text`.
Campos JSON: ementa, full_text, process, number, year, rapporteur,
collegiate, date, type, indicator, interested, subject, has_full_text.

Produz output compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from govy.api.tce_parser_v3 import (
    MISSING,
    REGION_MAP,
    classify_outcome_effect_from_dispositivo,
    classify_procedural_stage,
    detect_claim_patterns,
    extract_references,
    is_current_from_year,
    normalize_text,
)


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


def _format_date_go(raw_date: Any) -> str:
    """
    Converte data TCE-GO (formato 'DD/MM/YYYY HH:MM' ou 'DD/MM/YYYY') para 'DD/MM/YYYY'.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    return MISSING


def _build_acordao_numero(data: Dict[str, Any]) -> str:
    """Monta numero do acordao: '{number}/{year}'."""
    num = data.get("number")
    ano = data.get("year")
    if num is not None and ano is not None:
        return f"{num:05d}/{ano}" if isinstance(num, int) else f"{num}/{ano}"
    if num is not None:
        return str(num)
    return MISSING


def _build_tipo_documento(data: Dict[str, Any]) -> str:
    """Infere tipo de documento a partir de type/indicator."""
    tipo = data.get("type")
    indicator = data.get("indicator")
    if indicator:
        ind = str(indicator).strip().upper()
        if ind == "D":
            return "Decisao"
    if tipo:
        t = str(tipo).strip().upper()
        if "DECISAO" in t or "DECISÃO" in t:
            return "Decisao"
    return "Acordao"


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento."""
    year = data.get("year")
    if year is not None:
        try:
            y = int(year)
            if 1900 <= y <= 2100:
                return str(y)
        except (ValueError, TypeError):
            pass
    # Fallback: extrair do campo date
    date_val = data.get("date")
    if date_val:
        m = re.search(r"(\d{4})", str(date_val))
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2100:
                return str(y)
    return MISSING


def parse_tce_go_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TCE-GO (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se has_full_text==false ou full_text vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    has_ft = data.get("has_full_text")
    full_text_raw = data.get("full_text")

    if has_ft is False or has_ft == "false":
        return None
    if not full_text_raw or not str(full_text_raw).strip():
        return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("process"))
    acordao_numero = _build_acordao_numero(data)
    relator = _safe_str(data.get("rapporteur"))
    orgao_julgador = _safe_str(data.get("collegiate"))

    # --- Texto inline ---
    ementa = _safe_text(data.get("ementa"))
    full_text = _safe_text(full_text_raw)

    # dispositivo = full_text (texto completo do acordao)
    dispositivo = full_text

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(full_text)

    # claim_patterns: ementa + full_text
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if full_text != MISSING:
        claim_text += full_text
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect do dispositivo
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _format_date_go(data.get("date"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References (busca em todos os textos) ---
    all_text = " ".join(
        t for t in [ementa, full_text]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Campos adicionais ---
    interessado = _safe_str(data.get("interested"))
    assunto = _safe_str(data.get("subject"))
    tipo_documento = _build_tipo_documento(data)

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TCE",
        "tribunal_name": "TRIBUNAL DE CONTAS DO ESTADO DE GOIAS",
        "uf": "GO",
        "region": REGION_MAP.get("GO", "CENTRO_OESTE"),
        "processo": processo,
        "acordao_numero": acordao_numero,
        "relator": relator,
        "orgao_julgador": orgao_julgador,
        "ementa": ementa,
        "dispositivo": dispositivo,
        "holding_outcome": holding_outcome,
        "effect": effect,
        "publication_number": MISSING,
        "publication_date": MISSING,
        "julgamento_date": julgamento_date,
        "references": refs,
        "linked_processes": refs,
        "procedural_stage": stage,
        "claim_pattern": claim_patterns,
        "authority_score": "0.80",
        "year": year,
        "is_current": current,
        "key_citation": dispositivo if dispositivo != MISSING else MISSING,
        "key_citation_speaker": "TRIBUNAL" if dispositivo != MISSING else MISSING,
        "key_citation_source": "DISPOSITIVO" if dispositivo != MISSING else MISSING,
    }

    return out
