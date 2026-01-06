# src/govy/extractors/o001_objeto.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int


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
    stop_patterns = [
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
    for pat in stop_patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m and m.start() > 40:
            return s[: m.start()].strip()
    return s


def _normalize_object_text(s: str, max_len: int = 700) -> str:
    s = _clean_spaces(s)
    s = _stop_at_markers(s)

    # remove cabeçalhos repetidos tipo "OBJETO:" no começo
    s = re.sub(r"^\s*(?:DO\s+)?OBJETO\s*[:\-–]\s*", "", s, flags=re.IGNORECASE).strip()

    # limita tamanho
    if len(s) > max_len:
        s = s[:max_len].rsplit(".", 1)[0].strip()
        if not s.endswith("..."):
            s += "..."
    return s


def _find_candidates(text: str) -> List[Tuple[str, str, int]]:
    """
    Retorna lista de (objeto_normalizado, evidência, score)
    """
    t = text or ""
    cands: List[Tuple[str, str, int]] = []

    patterns = [
        # Ex.: "1. OBJETO: ...."
        (r"(?:^|\n)\s*(?:\d+[\.\)]\s*)?(?:DO\s+)?OBJETO\s*[:\-–]\s*(.{50,1200})", 9),
        # Ex.: "OBJETO DA LICITAÇÃO: ..."
        (r"(?:^|\n)\s*OBJETO\s+DA\s+LICITA[ÇC][ÃA]O\s*[:\-–]\s*(.{50,1200})", 9),
        # Ex.: "O presente edital tem por objeto ..."
        (r"\btem\s+(?:por|como)\s+objeto\s+(?:a|o|os|as)?\s*(.{50,1000})", 7),
        # Ex.: "Constitui objeto deste ..."
        (r"\bconstitui\s+objeto\s+(?:deste|da\s+presente)\s+(?:licita[çc][ãa]o|edital|contrata[çc][ãa]o)\s*(.{50,1000})", 7),
        # Ex.: "objeto: contratação de ..."
        (r"(?:^|\n)\s*objeto\s*[:\-–]\s*(?:contrata[çc][ãa]o|aquisi[çc][ãa]o|registro)\s+(.{50,1000})", 8),
    ]

    for pat, base_score in patterns:
        m = re.search(pat, t, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            continue

        full_match = m.group(0) or ""
        raw = m.group(1)
        raw = _clean_spaces(raw)
        raw = _stop_at_markers(raw)

        # pega evidência curta (até ~500 chars)
        ev = raw[:500]
        obj = _normalize_object_text(raw, max_len=700)

        # score bônus: palavras típicas de objeto
        bonus = 0
                # bônus forte se o trecho original encontrado contém "OBJETO" explícito
        if re.search(r"\b(?:DO\s+)?OBJETO\b", full_match, flags=re.IGNORECASE):
            bonus += 3

        low = obj.lower()
                # bônus forte se o trecho original tem "OBJETO" explícito (seção do edital)
        if re.search(r"\b(?:DO\s+)?OBJETO\b", raw, flags=re.IGNORECASE):
            bonus += 3

        if any(x in low for x in ["contratação", "contratacao", "aquisição", "aquisicao", "registro de preços", "registro de precos"]):
            bonus += 2
        if any(x in low for x in ["fornecimento", "prestação de serviços", "prestacao de servicos", "serviços", "servicos"]):
            bonus += 1

        score = base_score + bonus
        if len(obj) >= 40:
            cands.append((obj, ev, score))

    return cands


def extract_o001(text: str) -> ExtractResult:
    """
    O001 — Objeto da licitação.
    Retorna:
      - value: texto do objeto (normalizado)
      - evidence: trecho que embasou
      - score: confiança (heurística)
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    cands = _find_candidates(text)
    if not cands:
        return ExtractResult(value=None, evidence=None, score=0)

    # escolhe maior score; em empate, escolhe o mais longo (até o limite)
    cands.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
    best_obj, best_ev, best_score = cands[0]
    return ExtractResult(value=best_obj, evidence=best_ev, score=int(best_score))
