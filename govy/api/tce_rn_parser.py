"""
tce_rn_parser.py
Parser dedicado para TCE-RN (Rio Grande do Norte).

TCE-RN tem texto inline no JSON (ementa, relatorio, fundamentacaoVoto,
conclusao, textoAcordao) — nao precisa de PDF parsing.

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

# ----------------------------
# Lookup tables
# ----------------------------

CAMARA_LOOKUP = {
    1: "1a Camara",
    2: "2a Camara",
    3: "Plenario",
}


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


def _format_date(iso_date: Any) -> str:
    """Converte ISO date (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS) para DD/MM/YYYY."""
    if not iso_date:
        return MISSING
    s = str(iso_date).strip()
    # Tentar extrair YYYY-MM-DD do inicio
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        # Sanity check (rejeitar datas obviamente erradas como 3106-07-20)
        try:
            y = int(year)
            if y < 1900 or y > 2100:
                return MISSING
        except ValueError:
            return MISSING
        return f"{day}/{month}/{year}"
    return MISSING


def _build_processo(data: Dict[str, Any]) -> str:
    """Monta numero do processo: '{numero}/{ano}'."""
    num = data.get("numero_processo")
    ano = data.get("ano_processo")
    if num is not None and ano is not None:
        return f"{num}/{ano}"
    if num is not None:
        return str(num)
    return MISSING


def _build_acordao_numero(data: Dict[str, Any]) -> str:
    """Monta numero do acordao: '{numero}/{ano}'."""
    num = data.get("numero_resultado")
    ano = data.get("ano_resultado")
    if num is not None and ano is not None:
        return f"{num}/{ano}"
    if num is not None:
        return str(num)
    return MISSING


def _build_tipo_documento(resultado_tipo: Any) -> str:
    """A=Acordao, D=Decisao."""
    if not resultado_tipo:
        return "Acordao"
    t = str(resultado_tipo).strip().upper()
    if t == "D":
        return "Decisao"
    return "Acordao"


def _infer_year(data: Dict[str, Any]) -> str:
    """Infere ano do julgamento a partir das datas disponiveis."""
    for field in ("data_sessao", "data_publicacao"):
        val = data.get(field)
        if val:
            m = re.match(r"(\d{4})-", str(val))
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2100:
                    return str(y)
    # Fallback: ano_resultado ou ano_processo
    for field in ("ano_resultado", "ano_processo"):
        val = data.get(field)
        if val:
            try:
                y = int(val)
                if 1900 <= y <= 2100:
                    return str(y)
            except (ValueError, TypeError):
                pass
    return MISSING


def parse_tce_rn_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parseia um JSON do TCE-RN (blob de juris-raw) e produz output
    compativel com mapping_tce_to_kblegal.transform_parser_to_kblegal().

    Args:
        data: dict do JSON do blob (output do scraper build_metadata())

    Returns:
        dict com campos do parser (compativel com tce_parser_v3 output)
    """
    # --- Campos estruturados ---
    processo = _build_processo(data)
    acordao_numero = _build_acordao_numero(data)
    relator = _safe_str(data.get("relator"))
    codigo_camara = data.get("codigo_camara")
    orgao_julgador = CAMARA_LOOKUP.get(codigo_camara, MISSING) if codigo_camara else MISSING

    # --- Texto inline ---
    ementa = _safe_text(data.get("ementa"))
    texto_acordao = _safe_text(data.get("texto_acordao"))
    fundamentacao = _safe_text(data.get("fundamentacao_voto"))
    conclusao = _safe_text(data.get("conclusao"))
    relatorio = _safe_text(data.get("relatorio"))

    # dispositivo = texto_acordao (decisao do acordao)
    dispositivo = texto_acordao

    # --- Classificacoes (reusa logica do tce_parser_v3) ---
    # procedural_stage: ementa > fundamentacao > texto_acordao
    stage = classify_procedural_stage(ementa)
    if stage == MISSING:
        stage = classify_procedural_stage(fundamentacao)
    if stage == MISSING:
        stage = classify_procedural_stage(texto_acordao)

    # claim_patterns: ementa + fundamentacao
    claim_text = ""
    if ementa != MISSING:
        claim_text += ementa + " "
    if fundamentacao != MISSING:
        claim_text += fundamentacao
    claim_patterns = detect_claim_patterns(claim_text) if claim_text.strip() else []

    # outcome/effect do dispositivo
    holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)

    # --- Datas ---
    julgamento_date = _format_date(data.get("data_sessao"))
    publication_date = _format_date(data.get("data_publicacao"))
    year = _infer_year(data)
    current = is_current_from_year(year)

    # --- References (busca em todos os textos concatenados) ---
    all_text = " ".join(
        t for t in [ementa, fundamentacao, conclusao, relatorio, texto_acordao]
        if t != MISSING
    )
    refs = extract_references(all_text) if all_text.strip() else []

    # --- Campos adicionais ---
    interessado = _safe_str(data.get("interessado"))
    assunto = _safe_str(data.get("assunto"))
    tesauros = data.get("tesauros")
    tipo_documento = _build_tipo_documento(data.get("resultado_tipo"))

    # --- Monta output compativel com tce_parser_v3 ---
    out: Dict[str, Any] = {
        "tribunal_type": "TCE",
        "tribunal_name": "TRIBUNAL DE CONTAS DO ESTADO DO RIO GRANDE DO NORTE",
        "uf": "RN",
        "region": REGION_MAP.get("RN", "NORDESTE"),
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
        "authority_score": "0.80",
        "year": year,
        "is_current": current,
        "relatorio": relatorio,
        "fundamentacao": fundamentacao,
        "conclusao": conclusao,
        "key_citation": dispositivo if dispositivo != MISSING else MISSING,
        "key_citation_speaker": "TRIBUNAL" if dispositivo != MISSING else MISSING,
        "key_citation_source": "DISPOSITIVO" if dispositivo != MISSING else MISSING,
    }

    return out
