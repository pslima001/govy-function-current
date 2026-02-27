"""
stj_parser.py
Parser dedicado para STJ (Superior Tribunal de Justiça).

STJ usa 2 sub-bases (ACOR e BAEN) com mesmo formato JSON de 21 campos:
  num_registro, cdoc, base, classe_sigla, processo_display,
  processo_classe_full, processo_registro, relator, orgao_julgador,
  data_julgamento, data_publicacao, data_publicacao_raw, ementa,
  ementa_clean, acordao, referencia_legislativa, jurisprudencia_citada,
  inteiro_teor_url, processo_url, scraped_at, scraper_version

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


def _format_date_stj(raw_date: Any) -> str:
    """
    Converte data STJ para 'DD/MM/YYYY'.
    Formatos aceitos: 'DD/MM/YYYY', 'YYYY-MM-DD', ou string com data embutida.
    """
    if not raw_date:
        return MISSING
    s = str(raw_date).strip()
    # DD/MM/YYYY direto
    m = re.match(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    # ISO YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return MISSING


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano a partir de data_julgamento ou data_publicacao."""
    for field in ("data_julgamento", "data_publicacao"):
        date_val = data.get(field)
        if date_val:
            m = re.search(r"(\d{4})", str(date_val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    return MISSING


def _extract_refs_from_legislativa(ref_leg: str) -> List[str]:
    """
    Extrai referências legislativas do campo referencia_legislativa do STJ.
    Formato STJ: 'LEG:FED LEI:008666 ANO:1993\\n*****  LC-93  LEI DE LICITAÇÕES'
    """
    refs = []
    if not ref_leg or ref_leg == MISSING:
        return refs
    # Extrair padrões LEI:NNNNNN ANO:YYYY
    for m in re.finditer(r"LEI:(\d+)\s+ANO:(\d{4})", ref_leg):
        lei_num = str(int(m.group(1)))  # remove leading zeros
        ano = m.group(2)
        refs.append(f"Lei {lei_num}/{ano}")
    # Extrair LCP (Lei Complementar)
    for m in re.finditer(r"LCP:(\d+)\s+ANO:(\d{4})", ref_leg):
        lcp_num = str(int(m.group(1)))
        ano = m.group(2)
        refs.append(f"LC {lcp_num}/{ano}")
    # Extrair DEL (Decreto-Lei)
    for m in re.finditer(r"DEL:(\d+)\s+ANO:(\d{4})", ref_leg):
        del_num = str(int(m.group(1)))
        ano = m.group(2)
        refs.append(f"DL {del_num}/{ano}")
    # Extrair CFB (Constituição)
    if re.search(r"CFB:.*ANO:1988", ref_leg):
        refs.append("CF/1988")
    return refs


def parse_stj_json(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia um JSON do STJ (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Funciona para ambas sub-bases: ACOR e BAEN.

    Args:
        data: dict do JSON do blob (output do scraper)

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output),
        ou None se texto vazio (terminal_no_text).
    """
    # --- Check terminal_no_text ---
    ementa_raw = data.get("ementa") or data.get("ementa_clean")
    acordao_raw = data.get("acordao")

    # Se nem ementa nem acordao tem conteudo, terminal
    if not ementa_raw or not str(ementa_raw).strip():
        if not acordao_raw or not str(acordao_raw).strip():
            return None

    # --- Campos estruturados ---
    processo = _safe_str(data.get("processo_registro"))
    if processo == MISSING:
        processo = _safe_str(data.get("processo_display"))

    classe_sigla = _safe_str(data.get("classe_sigla"))
    processo_display = _safe_str(data.get("processo_display"))

    # acordao_numero: usar classe_sigla como identificador (ex: "CC 217033")
    acordao_numero = classe_sigla

    relator = _safe_str(data.get("relator"))
    # Limpar sufixo numerico do relator: "Ministro FULANO (1187)" -> "Ministro FULANO"
    if relator != MISSING:
        relator = re.sub(r"\s*\(\d+\)\s*$", "", relator)

    orgao_julgador = _safe_str(data.get("orgao_julgador"))

    # --- Texto inline ---
    ementa = _safe_text(ementa_raw)
    acordao = _safe_text(acordao_raw)

    # dispositivo = acordao (texto do acordao/voto)
    dispositivo = acordao

    # --- Datas ---
    julgamento_date = _format_date_stj(data.get("data_julgamento"))
    publication_date = _format_date_stj(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    stage = classify_procedural_stage(ementa if ementa != MISSING else "")
    if stage == MISSING and acordao != MISSING:
        stage = classify_procedural_stage(acordao)

    # claim_patterns
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if acordao != MISSING:
        claim_text += acordao
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(
        dispositivo if dispositivo != MISSING else ementa
    )

    # --- References ---
    # Combinar texto + campo referencia_legislativa do STJ
    all_text = " ".join(
        t for t in [ementa, acordao]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # Adicionar refs estruturadas do campo referencia_legislativa
    ref_legislativa = data.get("referencia_legislativa", "")
    if ref_legislativa:
        leg_refs = _extract_refs_from_legislativa(ref_legislativa)
        for r in leg_refs:
            if r not in refs:
                refs.append(r)

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "STJ",
        "tribunal_name": "SUPERIOR TRIBUNAL DE JUSTIÇA",
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
        "publication_date": publication_date,
        "julgamento_date": julgamento_date,
        "references": refs,
        "linked_processes": refs,
        "procedural_stage": stage,
        "claim_pattern": claim_patterns,
        "authority_score": "0.90",
        "year": year,
        "is_current": current,
        "key_citation": dispositivo if dispositivo != MISSING else ementa,
        "key_citation_speaker": "TRIBUNAL",
        "key_citation_source": "INTEIRO_TEOR" if dispositivo != MISSING else "EMENTA",
    }

    return out
