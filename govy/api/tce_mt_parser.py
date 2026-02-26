"""
tce_mt_parser.py
Parser dedicado para TCE-MT (Mato Grosso).

TCE-MT usa API REST ElasticSearch com texto inline completo no campo `texto_decisao`.
Campos JSON do scraper: doc_id, tribunal_id, es_id, numero_decisao, ano_decisao,
numero_ano_decisao, num_protocolo, ano_protocolo, numero_ano_protocolo,
tipo_decisao, colegiado, data_publicacao, ementa, texto_decisao,
keyword_match, processo_url, scraped_at.

Produz output compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

Inclui exclusao GOVY: itens com 'crime' ou 'criminal' sao rejeitados (terminal_excluded).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

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


def _format_date_mt(raw_date: Any) -> str:
    """
    Converte data TCE-MT (ISO 'YYYY-MM-DD' ou 'YYYY-MM-DDTHH:MM') para 'DD/MM/YYYY'.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return MISSING


def _build_acordao_numero(data: Dict[str, Any]) -> str:
    """Monta numero do acordao: '{numero_decisao}/{ano_decisao}'."""
    num = data.get("numero_decisao")
    ano = data.get("ano_decisao")
    if num is not None and ano is not None:
        return f"{num}/{ano}"
    numero_ano = data.get("numero_ano_decisao")
    if numero_ano:
        return str(numero_ano).replace("-", "/")
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento."""
    ano = data.get("ano_decisao")
    if ano is not None:
        try:
            y = int(ano)
            if 1900 <= y <= 2100:
                return str(y)
        except (ValueError, TypeError):
            pass
    # Fallback: extrair de data_publicacao
    date_val = data.get("data_publicacao")
    if date_val:
        m = re.search(r"(\d{4})", str(date_val))
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2100:
                return str(y)
    return MISSING


def parse_tce_mt_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do TCE-MT (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper_tce_mt.py)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto_decisao vazio (terminal_no_text) ou excluido
        por filtro GOVY crime/criminal (terminal_excluded).
    """
    # --- Check terminal_no_text ---
    texto_decisao_raw = data.get("texto_decisao")
    if not texto_decisao_raw or not str(texto_decisao_raw).strip():
        return None

    # --- GOVY exclusion: crime/criminal ---
    ementa_raw = data.get("ementa") or ""
    full_check = f"{ementa_raw} {texto_decisao_raw}"
    if _EXCLUSION_RE.search(full_check):
        return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("numero_ano_protocolo"))
    if processo == MISSING:
        # Fallback: montar de num_protocolo/ano_protocolo
        num_p = data.get("num_protocolo")
        ano_p = data.get("ano_protocolo")
        if num_p is not None and ano_p is not None:
            processo = f"{num_p}/{ano_p}"

    acordao_numero = _build_acordao_numero(data)
    orgao_julgador = _safe_str(data.get("colegiado"))

    # --- Texto inline ---
    ementa = _safe_text(ementa_raw)
    texto_decisao = _safe_text(texto_decisao_raw)

    # dispositivo = texto_decisao (texto completo do acordao)
    dispositivo = texto_decisao

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(texto_decisao)

    # claim_patterns: ementa + texto_decisao
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if texto_decisao != MISSING:
        claim_text += texto_decisao
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect do dispositivo
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    pub_date = _format_date_mt(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References (busca em todos os textos) ---
    all_text = " ".join(
        t for t in [ementa, texto_decisao]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TCE",
        "tribunal_name": "TRIBUNAL DE CONTAS DO ESTADO DE MATO GROSSO",
        "uf": "MT",
        "region": REGION_MAP.get("MT", "CENTRO_OESTE"),
        "processo": processo,
        "acordao_numero": acordao_numero,
        "relator": MISSING,
        "orgao_julgador": orgao_julgador,
        "ementa": ementa,
        "dispositivo": dispositivo,
        "holding_outcome": holding_outcome,
        "effect": effect,
        "publication_number": MISSING,
        "publication_date": pub_date,
        "julgamento_date": pub_date,
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
