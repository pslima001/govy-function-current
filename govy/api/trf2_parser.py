"""
trf2_parser.py
Parser dedicado para TRF2 (Tribunal Regional Federal da 2a Regiao).

TRF2 usa scraper requests+BS4 com Solr backend. JSONs contem:
- ementa (com tags HTML <BR />)
- full_text (texto concatenado limpo)
- inteiro_teor_acordao, inteiro_teor_voto, inteiro_teor_relatorio (opcionais)
- processo ja em formato CNJ, data_julgamento em DD/MM/YYYY

Produz output compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().
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


def _parse_date_ddmmyyyy(raw_date: Any) -> str:
    """Valida e retorna data DD/MM/YYYY. TRF2 ja usa esse formato."""
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento ou autuacao."""
    for field in ("data_julgamento", "data_autuacao"):
        date_val = data.get(field)
        if date_val:
            m = re.search(r"(\d{4})", str(date_val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    return MISSING


def _build_tipo_documento(data: Dict[str, Any]) -> str:
    """Infere tipo de documento a partir de tipo_julgamento e classe."""
    tipo = data.get("tipo_julgamento", "")
    if tipo:
        t = str(tipo).strip().upper()
        if "EMBARGO" in t:
            return "Acordao"
        if "MERITO" in t or "MÉRITO" in t:
            return "Acordao"
    classe = data.get("classe", "")
    if classe:
        c = str(classe).strip().upper()
        if any(k in c for k in ("AGRAVO", "RECURSO", "APELAÇÃO", "APELACAO",
                                  "MANDADO", "REMESSA")):
            return "Acordao"
    return "Acordao"


def parse_trf2_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TRF2 (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    full_text_raw = data.get("full_text")
    ementa_raw = data.get("ementa")

    if not full_text_raw or not str(full_text_raw).strip():
        if not ementa_raw or not str(ementa_raw).strip():
            return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("processo"))
    relator = _safe_str(data.get("relator"))
    orgao_julgador = _safe_str(data.get("competencia"))
    classe = _safe_str(data.get("classe"))

    # --- Texto inline ---
    full_text = _safe_text(full_text_raw)
    ementa = _safe_text(ementa_raw)

    # dispositivo = full_text (texto completo concatenado)
    dispositivo = full_text

    # --- Acordao numero (from doc_id) ---
    doc_id = data.get("doc_id", "")
    parts = doc_id.split("--")
    acordao_numero = MISSING
    if len(parts) >= 2:
        acordao_numero = parts[1]

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(full_text if full_text != MISSING else "")

    # claim_patterns
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if full_text != MISSING:
        claim_text += full_text
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _parse_date_ddmmyyyy(data.get("data_julgamento"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References ---
    all_text = " ".join(
        t for t in [ementa, full_text]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Tipo documento ---
    tipo_documento = _build_tipo_documento(data)

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TRF",
        "tribunal_name": "TRIBUNAL REGIONAL FEDERAL DA 2\u00aa REGI\u00c3O",
        "uf": None,
        "region": "SUDESTE",
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
        "authority_score": "0.85",
        "year": year,
        "is_current": current,
        "key_citation": dispositivo if dispositivo != MISSING else MISSING,
        "key_citation_speaker": "TRIBUNAL" if dispositivo != MISSING else MISSING,
        "key_citation_source": "INTEIRO_TEOR" if dispositivo != MISSING else MISSING,
    }

    return out
