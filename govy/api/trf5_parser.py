"""
trf5_parser.py
Parser dedicado para TRF5 (Tribunal Regional Federal da 5ª Região).

TRF5 usa API REST Julia Pesquisa com texto inline completo no campo `texto`.
33 campos JSON incluindo: texto, ementa, numero_processo, classe_judicial,
relator, orgao_julgador, data_julgamento, tipo_documento, etc.

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


def _format_date_trf5(raw_date: Any) -> str:
    """
    Converte data TRF5 (formato 'YYYY-MM-DD') para 'DD/MM/YYYY'.
    Aceita tambem 'DD/MM/YYYY' como fallback.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    # ISO format YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    # Already DD/MM/YYYY
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento."""
    date_val = data.get("data_julgamento")
    if date_val:
        m = re.search(r"(\d{4})", str(date_val))
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2100:
                return str(y)
    date_val = data.get("data_assinatura")
    if date_val:
        m = re.search(r"(\d{4})", str(date_val))
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2100:
                return str(y)
    return MISSING


def _build_tipo_documento(data: Dict[str, Any]) -> str:
    """Infere tipo de documento a partir de tipo_documento e classe_judicial."""
    tipo = data.get("tipo_documento")
    if tipo:
        t = str(tipo).strip().upper()
        if "EMENTA" in t:
            return "Acordao"
        if "DECISAO" in t or "DECISÃO" in t:
            return "Decisao"
        if "DESPACHO" in t:
            return "Despacho"
    classe = data.get("classe_judicial")
    if classe:
        c = str(classe).strip().upper()
        if "AGRAVO" in c or "RECURSO" in c or "APELAÇÃO" in c or "APELACAO" in c:
            return "Acordao"
    return "Acordao"


def _format_processo(numero_processo: Any) -> str:
    """Formata numero de processo CNJ (20 digitos) para formato legivel."""
    if not numero_processo:
        return MISSING
    s = str(numero_processo).strip()
    # Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
    if len(s) == 20 and s.isdigit():
        return f"{s[:7]}-{s[7:9]}.{s[9:13]}.{s[13]}.{s[14:16]}.{s[16:]}"
    return s


def parse_trf5_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TRF5 (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    texto_raw = data.get("texto")
    ementa_raw = data.get("ementa")

    # Se nem texto nem ementa tem conteudo, terminal
    if not texto_raw or not str(texto_raw).strip():
        if not ementa_raw or not str(ementa_raw).strip():
            return None

    # --- Campos estruturados ---
    processo = _format_processo(data.get("numero_processo"))
    relator = _safe_str(data.get("relator"))
    relator_acordao = _safe_str(data.get("relator_acordao"))
    if relator_acordao != MISSING and relator == MISSING:
        relator = relator_acordao
    orgao_julgador = _safe_str(data.get("orgao_julgador"))
    classe_judicial = _safe_str(data.get("classe_judicial"))

    # --- Texto inline ---
    texto = _safe_text(texto_raw)
    ementa = _safe_text(ementa_raw)

    # Se ementa vazia mas texto contem "E M E N T A", tentar extrair
    if ementa == MISSING and texto != MISSING:
        # Muitos TRF5 docs tem ementa inline no texto
        ementa_match = re.search(
            r"E\s*M\s*E\s*N\s*T\s*A\s*\n(.*?)(?:\n\s*(?:A\s*C\s*[ÓO]\s*R\s*D\s*[ÃA]\s*O|V\s*O\s*T\s*O|R\s*E\s*L\s*A\s*T\s*[ÓO]\s*R\s*I\s*O)|$)",
            texto, re.DOTALL | re.IGNORECASE,
        )
        if ementa_match:
            extracted = normalize_text(ementa_match.group(1))
            if len(extracted) >= 20:
                ementa = extracted

    # dispositivo = texto completo
    dispositivo = texto

    # --- Acordao numero (from doc_id) ---
    doc_id = data.get("doc_id", "")
    parts = doc_id.split("--")
    acordao_numero = MISSING
    if len(parts) >= 2:
        acordao_numero = parts[1]  # processo_id from doc_id

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(texto)

    # claim_patterns
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if texto != MISSING:
        claim_text += texto
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _format_date_trf5(data.get("data_julgamento"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References ---
    all_text = " ".join(
        t for t in [ementa, texto]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Tipo documento ---
    tipo_documento = _build_tipo_documento(data)

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TRF",
        "tribunal_name": "TRIBUNAL REGIONAL FEDERAL DA 5ª REGIÃO",
        "uf": None,
        "region": "NORDESTE",
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
