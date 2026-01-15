# src/govy/extractors/o001_objeto.py
from __future__ import annotations

import re

from govy.extractors.config.loader import get_extractor_config
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int


# --- Config via patterns.json (com fallback) ---
_CFG_O001 = get_extractor_config("o001_objeto") or {}

# Stop markers (seções que normalmente vêm após o OBJETO)
# Se o patterns.json fornecer "stop_markers", eles serão convertidos em regex.
_DEFAULT_STOP_PATTERNS = [
    r"\bDA\s+JUSTIFICATIVA\b",
    r"\bDO\s+VALOR\b",
    r"\bDA\s+VIG[ÊE]NCIA\b",
    r"\bDAS\s+CONDI[ÇC][ÕO]ES\b",
    r"\bCRIT[ÉE]RIO\s+DE\s+JULGAMENTO\b",
    r"\bDA\s+HABILITA[ÇC][ÃA]O\b",
    r"\bDO\s+PAGAMENTO\b",
    r"\bDA\s+ENTREGA\b",
    r"\bDOS\s+PRAZOS\b",
    r"\bDISPOSI[ÇC][ÕO]ES\s+GERAIS\b",
    r"\bA\s+AQUISI[ÇC][ÃA]O\s+SER[ÁA]\b",
    r"\bA\s+AQUISI[ÇC][ÃA]O\s+SER[ÁA]\s+DIVIDIDA\b",
    r"\bSER[ÁA]\s+DIVIDIDA\s+EM\b",
    r"\bCONFORME\s+TERMO\s+DE\s+REFER[ÊE]NCIA\b",
    r"\bANEXO\s+I\b",
    r"\bTERMO\s+DE\s+REFER[ÊE]NCIA\b",
]


def _marker_to_regex(marker: str) -> str:
    # Converte "DO VALOR" -> r"\bDO\s+VALOR\b"
    marker = marker.strip()
    if not marker:
        return ""
    parts = [re.escape(p) for p in marker.split()]
    return r"\b" + r"\s+".join(parts) + r"\b"


_STOP_MARKERS = _CFG_O001.get("stop_markers", None)
if isinstance(_STOP_MARKERS, list) and _STOP_MARKERS:
    STOP_PATTERNS = [p for p in (_marker_to_regex(m) for m in _STOP_MARKERS) if p]
else:
    STOP_PATTERNS = list(_DEFAULT_STOP_PATTERNS)

# Termos bônus (ajudam a escolher o candidato mais "objeto")
_DEFAULT_BONUS_TERMS = [
    "contratação", "contratacao", "aquisição", "aquisicao", "registro de preços", "registro de precos",
    "fornecimento", "prestação de serviços", "prestacao de servicos", "serviços", "servicos"
]
BONUS_TERMS = _CFG_O001.get("bonus_termos", _DEFAULT_BONUS_TERMS)
if not isinstance(BONUS_TERMS, list):
    BONUS_TERMS = list(_DEFAULT_BONUS_TERMS)


def _clean_spaces(s: str) -> str:
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _stop_at_markers(s: str) -> str:
    """
    Corta o objeto quando começam seções típicas seguintes.
    Ajustável conforme editais.
    """
    stop_patterns = STOP_PATTERNS
    for pat in stop_patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            return s[: m.start()].strip()
    return s.strip()


def _normalize_object_text(s: str, max_len: int = 700) -> str:
    s = _clean_spaces(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "..."
    return s


def _extract_candidates(text: str) -> List[Tuple[str, str, int]]:
    """
    Retorna lista de candidatos: (objeto_normalizado, evidencia_curta, score)
    """
    if not text:
        return []

    patterns = [
        r"\b(?:DO\s+)?OBJETO\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
        r"\bOBJETO\s+DA\s+LICITA[ÇC][ÃA]O\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
        r"\bOBJETO\s+DO\s+CERTAME\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
    ]

    cands: List[Tuple[str, str, int]] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE | re.DOTALL):
            full_match = m.group(0) or ""
            raw = m.group(1)
            raw = _clean_spaces(raw)
            raw = _stop_at_markers(raw)

            # pega evidência curta (até ~500 chars)
            ev = raw[:500]
            obj = _normalize_object_text(raw, max_len=700)

            base_score = 10
            bonus = 0

            # bônus forte se o trecho original encontrado contém "OBJETO" explícito
            if re.search(r"\b(?:DO\s+)?OBJETO\b", full_match, flags=re.IGNORECASE):
                bonus += 3
            if re.search(r"\b(?:DO\s+)?OBJETO\b", raw, flags=re.IGNORECASE):
                bonus += 3

            low = obj.lower()
            if any(str(x).lower() in low for x in BONUS_TERMS):
                bonus += 2
            if any(str(x).lower() in low for x in BONUS_TERMS):
                bonus += 1

            score = base_score + bonus
            if len(obj) >= 40:
                cands.append((obj, ev, score))

    return cands


def extract_o001(text: str) -> ExtractResult:
    """
    O001 — Objeto da licitação.
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    cands = _extract_candidates(text)
    if not cands:
        return ExtractResult(value=None, evidence=None, score=0)

    cands.sort(key=lambda x: x[2], reverse=True)
    best_obj, best_ev, best_score = cands[0]
    return ExtractResult(value=best_obj, evidence=best_ev, score=int(best_score))
