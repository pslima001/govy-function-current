"""
stf_parser.py
Parser dedicado para STF (Supremo Tribunal Federal).

STF usa Elasticsearch API com texto inline em ementa_texto e acordao_ata.
Tres tipos de documento: sjur (regular), repercussao-geral (RG thesis), colac (historico/degradado).

Produz output compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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


def _format_date_iso(raw_date: Any) -> str:
    """
    Converte data ISO (formato 'YYYY-MM-DD' ou 'YYYY-MM-DDThh:mm:ss') para 'DD/MM/YYYY'.
    Aceita tambem 'DD/MM/YYYY' como fallback.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    # ISO format YYYY-MM-DD (com ou sem hora)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    # Already DD/MM/YYYY
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    return MISSING


def _infer_year(inner: Dict[str, Any]) -> str:
    """Infere ano do julgamento a partir de julgamento_data ou publicacao_data."""
    for field in ("julgamento_data", "publicacao_data"):
        date_val = inner.get(field)
        if date_val:
            m = re.search(r"(\d{4})", str(date_val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    return MISSING


def _detect_doc_type(inner: Dict[str, Any]) -> str:
    """Detecta tipo de documento STF: Acordao, Repercussao Geral, etc."""
    doc_id = str(inner.get("id", ""))
    if doc_id.startswith("repercussao-geral"):
        return "Repercussao Geral"
    classe = _safe_str(inner.get("classe_sigla"))
    if classe != MISSING:
        c = classe.upper()
        if "ADI" in c or "ADPF" in c or "ADC" in c or "ADO" in c:
            return "Acordao"
    return "Acordao"


def parse_stf_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do STF (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper, com envelope ou sem)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Unwrap envelope ---
    inner = data.get("data", data)

    # --- Check terminal_no_text ---
    ementa_raw = inner.get("ementa_texto")
    acordao_raw = inner.get("acordao_ata")

    if not ementa_raw or not str(ementa_raw).strip():
        if not acordao_raw or not str(acordao_raw).strip():
            return None

    # --- Campos estruturados ---
    processo = _safe_str(inner.get("processo_codigo_completo"))
    relator = _safe_str(inner.get("relator_processo_nome"))
    relator_acordao = _safe_str(inner.get("relator_acordao_nome"))
    if relator == MISSING and relator_acordao != MISSING:
        relator = relator_acordao
    orgao_julgador = _safe_str(inner.get("orgao_julgador"))

    # --- Texto inline ---
    ementa = _safe_text(ementa_raw)
    dispositivo = _safe_text(acordao_raw)

    # --- Acordao numero (from inner id or envelope doc_id) ---
    acordao_numero = _safe_str(inner.get("id"))
    if acordao_numero == MISSING:
        acordao_numero = _safe_str(data.get("doc_id"))

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(dispositivo)

    # claim_patterns
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if dispositivo != MISSING:
        claim_text += dispositivo
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _format_date_iso(inner.get("julgamento_data"))
    publication_date = _format_date_iso(inner.get("publicacao_data"))
    year = _infer_year(inner)
    current = is_current_from_year(year)

    # --- References ---
    # Combine ementa + acordao + legislacao_citada
    all_text_parts: List[str] = []
    if ementa != MISSING:
        all_text_parts.append(ementa)
    if dispositivo != MISSING:
        all_text_parts.append(dispositivo)

    # legislacao citada pode ser array ou texto
    leg_citada = inner.get("documental_legislacao_citada_texto")
    if leg_citada:
        if isinstance(leg_citada, list):
            all_text_parts.extend(str(x) for x in leg_citada if x)
        elif isinstance(leg_citada, str):
            all_text_parts.append(leg_citada)

    all_text = " ".join(all_text_parts)
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Key citation: tese de RG se disponivel ---
    tese_rg = inner.get("documental_tese_texto")
    if tese_rg and str(tese_rg).strip():
        key_citation = normalize_text(str(tese_rg))
        key_citation_speaker = "TRIBUNAL"
        key_citation_source = "TESE_RG"
    elif dispositivo != MISSING:
        key_citation = dispositivo
        key_citation_speaker = "TRIBUNAL"
        key_citation_source = "INTEIRO_TEOR"
    else:
        key_citation = MISSING
        key_citation_speaker = MISSING
        key_citation_source = MISSING

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "STF",
        "tribunal_name": "SUPREMO TRIBUNAL FEDERAL",
        "uf": None,
        "region": None,
        "processo": processo,
        "acordao_numero": acordao_numero,
        "relator": relator,
        "orgao_julgador": orgao_julgador,
        "ementa": ementa,
        "dispositivo": dispositivo,
        "holding_outcome": holding_outcome,
        "effect": effect,
        "publication_number": MISSING,
        "publication_date": publication_date,
        "julgamento_date": julgamento_date,
        "references": refs,
        "linked_processes": refs,
        "procedural_stage": stage,
        "claim_pattern": claim_patterns,
        "authority_score": "0.95",
        "year": year,
        "is_current": current,
        "key_citation": key_citation,
        "key_citation_speaker": key_citation_speaker,
        "key_citation_source": key_citation_source,
    }

    return out
