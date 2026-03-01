"""
govy.matching - Matching determinístico de itens de edital contra bulas/fichas.

Módulo separado do extract_items.py (ETL de itens).
Consome dados já extraídos (item_id + descrição do TR) e compara
contra textos de bulas/fichas/URLs do cliente.

Uso típico:
    from govy.matching import (
        parse_medicine_requirement_from_item_description,
        match_item_to_bula,
        format_popup,
        WaiverConfig,
    )

    req = parse_medicine_requirement_from_item_description(descricao_item)
    result = match_item_to_bula("38", req, texto_bula)
    print(format_popup(result, req))

Versão: v1.0.0-mvp
"""
__version__ = "1.0.0-mvp"

from .models import (
    GapCode,
    GAP_COMPACT,
    ItemRequirement,
    Presentation,
    Gap,
    MatchResult,
    WaiverConfig,
)
from .normalizers import normalize_text, parse_number
from .parsers import (
    parse_medicine_requirement_from_item_description,
    extract_presentations_from_bula_text,
)
from .matcher import match_item_to_bula, format_popup
from .pdf_utils import extract_text_from_pdf

__all__ = [
    # models
    "GapCode",
    "GAP_COMPACT",
    "ItemRequirement",
    "Presentation",
    "Gap",
    "MatchResult",
    "WaiverConfig",
    # normalizers
    "normalize_text",
    "parse_number",
    # parsers
    "parse_medicine_requirement_from_item_description",
    "extract_presentations_from_bula_text",
    # matcher
    "match_item_to_bula",
    "format_popup",
    # pdf
    "extract_text_from_pdf",
]
