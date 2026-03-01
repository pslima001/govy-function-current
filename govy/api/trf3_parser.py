"""
trf3_parser.py
Parser dedicado para TRF3 (Tribunal Regional Federal da 3a Regiao).

TRF3 usa scraper Selenium com ementa + inteiro teor embedded no HTML.
Campos chave: ementa, inteiro_teor, processo, classe, classe_sigla,
turma, relator, data_julgamento, data_publicacao.

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
    """
    Valida e retorna data DD/MM/YYYY. TRF3 ja usa esse formato.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento ou publicacao."""
    for field in ("data_julgamento", "data_publicacao"):
        date_val = data.get(field)
        if date_val:
            m = re.search(r"(\d{4})", str(date_val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    return MISSING


def _build_tipo_documento(data: Dict[str, Any]) -> str:
    """Infere tipo de documento a partir de classe e tipo."""
    tipo = data.get("tipo", "")
    if tipo:
        t = str(tipo).strip().upper()
        if "ACORDAO" in t or "ACÓRDÃO" in t:
            return "Acordao"
        if "DECISAO" in t or "DECISÃO" in t:
            return "Decisao"
    classe = data.get("classe", "")
    if classe:
        c = str(classe).strip().upper()
        if any(k in c for k in ("AGRAVO", "RECURSO", "APELAÇÃO", "APELACAO",
                                  "MANDADO", "REMESSA")):
            return "Acordao"
    return "Acordao"


def parse_trf3_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TRF3 (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    inteiro_teor_raw = data.get("inteiro_teor")
    ementa_raw = data.get("ementa")

    # Se nem inteiro_teor nem ementa tem conteudo, terminal
    if not inteiro_teor_raw or not str(inteiro_teor_raw).strip():
        if not ementa_raw or not str(ementa_raw).strip():
            return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("processo"))
    relator = _safe_str(data.get("relator"))
    orgao_julgador = _safe_str(data.get("turma"))
    classe = _safe_str(data.get("classe"))
    classe_sigla = _safe_str(data.get("classe_sigla"))

    # --- Texto inline ---
    inteiro_teor = _safe_text(inteiro_teor_raw)
    ementa = _safe_text(ementa_raw)

    # Se ementa vazia mas inteiro_teor contem "E M E N T A", tentar extrair
    if ementa == MISSING and inteiro_teor != MISSING:
        ementa_match = re.search(
            r"E\s*M\s*E\s*N\s*T\s*A\s*\n(.*?)(?:\n\s*(?:A\s*C\s*[ÓO]\s*R\s*D\s*[ÃA]\s*O|V\s*O\s*T\s*O|R\s*E\s*L\s*A\s*T\s*[ÓO]\s*R\s*I\s*O)|$)",
            inteiro_teor, re.DOTALL | re.IGNORECASE,
        )
        if ementa_match:
            extracted = normalize_text(ementa_match.group(1))
            if len(extracted) >= 20:
                ementa = extracted

    # dispositivo = inteiro teor completo
    dispositivo = inteiro_teor

    # --- Acordao numero (from doc_id) ---
    doc_id = data.get("doc_id", "")
    parts = doc_id.split("--")
    acordao_numero = MISSING
    if len(parts) >= 2:
        acordao_numero = parts[1]

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(inteiro_teor if inteiro_teor != MISSING else "")

    # claim_patterns
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if inteiro_teor != MISSING:
        claim_text += inteiro_teor
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _parse_date_ddmmyyyy(data.get("data_julgamento"))
    publication_date = _parse_date_ddmmyyyy(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References ---
    all_text = " ".join(
        t for t in [ementa, inteiro_teor]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Tipo documento ---
    tipo_documento = _build_tipo_documento(data)

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TRF",
        "tribunal_name": "TRIBUNAL REGIONAL FEDERAL DA 3\u00aa REGI\u00c3O",
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
        "publication_date": publication_date,
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
