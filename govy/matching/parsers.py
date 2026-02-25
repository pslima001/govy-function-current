"""
govy.matching.parsers — Regex patterns e funções de parsing para matching.

Duas funções principais:
1. parse_medicine_requirement_from_item_description()
   - Interpreta a descrição já extraída do item (vinda do BD/extract_items)
   - NÃO extrai itens do edital (isso é papel do extract_items.py)

2. extract_presentations_from_bula_text()
   - Detecta apresentações (concentração, forma, volume) em texto de bula/ficha
"""
from __future__ import annotations

import re
from typing import List

from .models import ItemRequirement, Presentation
from .normalizers import normalize_text, parse_number


# =============================================================================
# REGEX PATTERNS
# =============================================================================

# Item do edital/TR estruturado: PRINCIPIO; 10 MG/ML; FORMA <PKG> <VOL> ML
RE_ITEM_STRUCTURED = re.compile(
    r"""(?is)^\s*
    (?P<principio>[^;]+?)\s*;\s*
    (?P<conc_num>\d{1,4}(?:\.\d{3})*(?:,\d+)?)\s*
    (?P<conc_unit>MG|MCG|G|UI)\s*/\s*
    (?P<conc_den>ML|L)\s*;\s*
    (?P<forma>.+?)\s+
    (?P<pkg>FRASCO-AMPOLA|AMPOLA|FRASCO|SERINGA)\s*
    (?P<vol>\d{1,3}(?:,\d+)?)\s*
    (?P<vol_unit>ML|L)\s*$
    """,
    re.VERBOSE,
)

# Bula: dose/volume explícito (ex: 500 MG / 50 ML)
RE_DOSE_PER_VOL = re.compile(
    r"(?i)\b(?P<dose>\d{1,4}(?:\.\d{3})*(?:,\d+)?)\s*"
    r"(?P<dose_unit>MG|MCG|G|UI)\s*/\s*"
    r"(?P<vol>\d{1,3}(?:,\d+)?)\s*(?P<vol_unit>ML|L)\b"
)

# Bula: concentração explícita sem denominador numérico (ex: 10 MG/ML)
RE_CONC = re.compile(
    r"(?i)\b(?P<num>\d{1,4}(?:\.\d{3})*(?:,\d+)?)\s*"
    r"(?P<num_unit>MG|MCG|G|UI)\s*/\s*(?P<den_unit>ML|L)\b"
)

# Bula: forma farmacêutica (lista estrita — MVP)
RE_FORM = re.compile(
    r"(?i)\b("
    r"SOLUCAO\s+INJETAVEL|"
    r"SOLUCAO\s+PARA\s+DILUICAO\s+PARA\s+INFUSAO|"
    r"SOLUCAO\s+PARA\s+INFUSAO|"
    r"PO\s+LIOFILIZADO\s+INJETAVEL|"
    r"COMPRIMIDO|"
    r"CAPSULA"
    r")\b"
)

# Bula: embalagem + volume próximo (ex: FRASCO-AMPOLA ... 50 ML)
RE_PKG_VOL = re.compile(
    r"(?i)\b(?P<pkg>FRASCO-AMPOLA|AMPOLA|FRASCO|SERINGA)\b"
    r".{0,40}?"
    r"\b(?P<vol>\d{1,3}(?:,\d+)?)\s*(?P<unit>ML|L)\b"
)


# =============================================================================
# PARSERS
# =============================================================================

def parse_medicine_requirement_from_item_description(item_raw: str) -> ItemRequirement:
    """
    Faz parsing da descrição do item do edital/TR (texto MAIS completo).

    Espera formato estruturado com separadores ';' e apresentação com volume.
    Exemplo: "RITUXIMABE; 10 MG/ML; SOLUÇÃO INJETÁVEL  FRASCO-AMPOLA 50 ML"

    Raises:
        ValueError: se o texto não casa no padrão estruturado MVP.
    """
    raw_norm = normalize_text(item_raw)
    m = RE_ITEM_STRUCTURED.match(raw_norm)
    if not m:
        raise ValueError(
            f"Item nao casa no padrao estruturado MVP: {item_raw!r}"
        )

    return ItemRequirement(
        raw=item_raw,
        principle=m.group("principio").strip(),
        conc_num=parse_number(m.group("conc_num")),
        conc_unit=normalize_text(m.group("conc_unit")),
        conc_den_unit=normalize_text(m.group("conc_den")),
        form=normalize_text(m.group("forma")),
        pkg=normalize_text(m.group("pkg")),
        vol=parse_number(m.group("vol")),
        vol_unit=normalize_text(m.group("vol_unit")),
    )


def _short_evidence(text: str, start: int, end: int, window: int = 70) -> str:
    """Extrai trecho curto ao redor do match para evidência."""
    left = max(0, start - window)
    right = min(len(text), end + window)
    snippet = text[left:right].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:220]


def extract_presentations_from_bula_text(bula_text: str) -> List[Presentation]:
    """
    Extrai apresentações de bula/ficha técnica.

    Estratégia (MVP):
    1. Busca padrões dose/volume (ex: 500 MG/50 ML) → deriva concentração
    2. Se não achou, busca concentração explícita (ex: 10 MG/ML)
    3. Detecta forma farmacêutica (primeira ocorrência global — MVP)

    Returns:
        Lista de Presentation encontradas. Pode ser vazia.
    """
    t = normalize_text(bula_text)
    presentations: List[Presentation] = []

    # forma: primeira ocorrência (MVP)
    form_match = RE_FORM.search(t)
    found_form = normalize_text(form_match.group(1)) if form_match else None

    # 1) Apresentações do tipo DOSE/VOL (500 MG/50 ML)
    for m in RE_DOSE_PER_VOL.finditer(t):
        dose = parse_number(m.group("dose"))
        dose_unit = normalize_text(m.group("dose_unit"))
        vol = parse_number(m.group("vol"))
        vol_unit = normalize_text(m.group("vol_unit"))

        # Derivar concentração (MVP)
        conc_num = None
        conc_unit = dose_unit
        conc_den_unit = vol_unit

        if vol_unit == "L":
            conc_num = dose / (vol * 1000.0) if vol else None
            conc_den_unit = "ML"
        else:
            conc_num = dose / vol if vol else None

        ev = _short_evidence(t, m.start(), m.end())
        presentations.append(Presentation(
            dose=dose,
            dose_unit=dose_unit,
            vol=vol,
            vol_unit=vol_unit,
            conc_num=conc_num,
            conc_unit=conc_unit,
            conc_den_unit=conc_den_unit,
            form=found_form,
            evidence=ev,
        ))

    # 2) Fallback: concentração explícita (10 MG/ML) se não achou dose/vol
    if not presentations:
        for m in RE_CONC.finditer(t):
            conc_num = parse_number(m.group("num"))
            conc_unit = normalize_text(m.group("num_unit"))
            conc_den_unit = normalize_text(m.group("den_unit"))

            ev = _short_evidence(t, m.start(), m.end())
            presentations.append(Presentation(
                dose=None, dose_unit=None,
                vol=None, vol_unit=None,
                conc_num=conc_num, conc_unit=conc_unit, conc_den_unit=conc_den_unit,
                form=found_form,
                evidence=ev,
            ))

    return presentations
