"""
trf6_parser.py
Parser dedicado para TRF6 (Tribunal Regional Federal da 6a Regiao).

TRF6 usa eproc (mesmo sistema do TRF4). Scraper v1.0 grava 2 blobs/doc:
  metadata.json (com ementa, decisao, full_text ja extraido do HTML)
  inteiro_teor.html

O campo `full_text` ja vem extraido pelo scraper — parser nao precisa ler HTML.

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
    """Valida e retorna data DD/MM/YYYY."""
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


def _clean_processo(processo: Any) -> str:
    """Remove sufixo /TRF6 do numero de processo."""
    if not processo:
        return MISSING
    s = str(processo).strip()
    # Remove /TRF6 suffix
    s = re.sub(r'/TRF\d+$', '', s)
    return s if s else MISSING


def parse_trf6_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um metadata.json do TRF6 (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do metadata.json do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    full_text_raw = data.get("full_text")
    ementa_raw = data.get("ementa")
    decisao_raw = data.get("decisao")

    # Se nenhum campo de texto tem conteudo, terminal
    has_full_text = full_text_raw and len(str(full_text_raw).strip()) >= 10
    has_ementa = ementa_raw and len(str(ementa_raw).strip()) >= 10
    has_decisao = decisao_raw and len(str(decisao_raw).strip()) >= 10

    if not has_full_text and not has_ementa and not has_decisao:
        return None

    # --- Campos estruturados ---
    processo = _clean_processo(data.get("processo"))
    relator = _safe_str(data.get("relator"))
    relator_acordao = _safe_str(data.get("relator_acordao"))
    if relator_acordao != MISSING and relator == MISSING:
        relator = relator_acordao
    orgao_julgador = _safe_str(data.get("orgao_julgador"))

    # --- Texto ---
    full_text = _safe_text(full_text_raw)
    ementa = _safe_text(ementa_raw)
    decisao = _safe_text(decisao_raw)

    # dispositivo = full_text (inteiro teor completo) ou fallback para decisao
    if full_text != MISSING:
        dispositivo = full_text
    elif decisao != MISSING:
        dispositivo = decisao
    else:
        dispositivo = ementa

    # Se ementa vazia mas full_text contem "E M E N T A", tentar extrair
    if ementa == MISSING and full_text != MISSING:
        ementa_match = re.search(
            r"E\s*M\s*E\s*N\s*T\s*A\s*\n(.*?)(?:\n\s*(?:A\s*C\s*[ÓO]\s*R\s*D\s*[ÃA]\s*O|V\s*O\s*T\s*O|R\s*E\s*L\s*A\s*T\s*[ÓO]\s*R\s*I\s*O)|$)",
            full_text, re.DOTALL | re.IGNORECASE,
        )
        if ementa_match:
            extracted = normalize_text(ementa_match.group(1))
            if len(extracted) >= 20:
                ementa = extracted

    # --- Acordao numero (from doc_id) ---
    doc_id = data.get("doc_id", "")
    parts = doc_id.split("--")
    acordao_numero = MISSING
    if len(parts) >= 2:
        acordao_numero = parts[1]

    # --- Classificacoes ---
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
    publication_date = _parse_date_ddmmyyyy(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References ---
    all_text = " ".join(
        t for t in [ementa, full_text]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TRF",
        "tribunal_name": "TRIBUNAL REGIONAL FEDERAL DA 6\u00aa REGI\u00c3O",
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
        "key_citation_source": "INTEIRO_TEOR" if full_text != MISSING else "DECISAO",
    }

    return out
