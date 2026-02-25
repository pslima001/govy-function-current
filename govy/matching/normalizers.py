"""
govy.matching.normalizers — Normalização de texto para matching de medicamentos.

Funções de limpeza/normalização específicas para comparação entre
descrições de TR/edital e textos de bulas/fichas técnicas.
"""
from __future__ import annotations

import re
import unicodedata


def _strip_accents(s: str) -> str:
    """Remove acentos/diacríticos (NFD decomposition)."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize_text(s: str) -> str:
    """
    Normalização mínima (MVP):
    - upper
    - remove acentos
    - remove hifenização de quebra de linha (PDF)
    - normaliza espaços
    - normaliza µg/IU/mL → MCG/UI/ML
    - normaliza FRASCO-AMPOLA variantes
    """
    if not s:
        return ""

    # colar hifenização de quebra de linha (para PDF extraído)
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)

    s = s.replace("\t", " ")
    s = _strip_accents(s)
    s = s.upper()

    # normalizar micrograma e IU
    s = s.replace("µG", "MCG")
    s = s.replace("UG", "MCG")
    s = s.replace("IU", "UI")

    # normalizar mL
    s = s.replace("M L", "ML")
    s = s.replace("M/L", "ML")

    # normalizar FRASCO-AMPOLA variantes
    s = re.sub(r"\bFRASCO\s*-\s*AMPOLA\b", "FRASCO-AMPOLA", s)
    s = re.sub(r"\bFRASCO\s+AMPOLA\b", "FRASCO-AMPOLA", s)

    # espaços
    s = re.sub(r"[ ]{2,}", " ", s).strip()
    return s


def parse_number(num_str: str) -> float:
    """
    Converte string numérica pt-BR para float.

    Exemplos:
      '10.000'  → 10000.0  (milhar)
      '1.000'   → 1000.0   (milhar)
      '10,5'    → 10.5     (decimal)
      '1.000,5' → 1000.5   (milhar + decimal)
    """
    if num_str is None:
        raise ValueError("num_str vazio")

    num_str = num_str.strip()

    # ambíguo: ponto milhar + vírgula decimal (padrão BR)
    if "," in num_str and "." in num_str:
        num_str = num_str.replace(".", "").replace(",", ".")
    elif "," in num_str:
        num_str = num_str.replace(",", ".")
    else:
        # só ponto: milhar quando houver 3 dígitos após (ex: 10.000)
        if re.search(r"\.\d{3}\b", num_str):
            num_str = num_str.replace(".", "")
    return float(num_str)
