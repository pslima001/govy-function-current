# src/govy/extractors/pg001_pagamento.py
from __future__ import annotations

import re
import unicodedata

from govy.extractors.config.loader import get_extractor_config
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int


def _norm(s: str) -> str:
    s = s.lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def extract_pg001(text: str) -> ExtractResult:
    """
    PG001 — Prazo de Pagamento
    Estratégia:
      - procurar padrões de número + dias (úteis/corridos)
      - dar score por contexto (pagamento, nota fiscal, liquidação, etc.)
      - evitar capturar prazos de entrega/vigência/recurso etc.
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    cfg = get_extractor_config("pg001_pagamento")
    regex_principal = cfg.get(
        "regex_principal",
        r"(\d{1,3})\s*(?:\([\w\sçãáéíóúõâêô.-]{0,25}\))?\s*dias?\s*(?:úteis|uteis|corridos)?",
    )

    padrao = re.compile(
        regex_principal,
        re.IGNORECASE
    )

    DEFAULT_POSITIVOS = [
        "pagamento", "pagar", "liquidação", "liquidacao", "nota fiscal", "nf",
        "fatura", "empenho", "atesto", "liquidar"
    ]
    DEFAULT_NEGATIVOS = [
        "entrega", "fornecimento", "execução", "execucao", "vigência", "vigencia",
        "recurso", "impugna", "amostra", "proposta", "validade", "garantia"
    ]
    threshold_score = int(cfg.get("threshold_score", 2))

    contexto = cfg.get("contexto", {}) if isinstance(cfg.get("contexto", {}), dict) else {}
    positivos = contexto.get("positivos", DEFAULT_POSITIVOS)
    negativos = contexto.get("negativos", DEFAULT_NEGATIVOS)

    positivos_n = [_norm(p) for p in positivos]
    negativos_n = [_norm(n) for n in negativos]

    best_num = None
    best_ctx = None
    best_score = -10

    for m in padrao.finditer(text):
        num = m.group(1)
        pos = m.start()
        ctx = text[max(0, pos - 250): min(len(text), pos + 250)]
        ctx_low = ctx.lower()
        ctx_n = _norm(ctx)

        score = 0
        score += sum(2 for p in positivos_n if p and p in ctx_n)
        score -= sum(3 for n in negativos_n if n and n in ctx_n)

        # bônus por frases típicas
        if "prazo" in ctx_low and ("pagamento" in ctx_low or "liquidação" in ctx_low or "liquidacao" in ctx_low):
            score += 3
        if "prazo de pagamento" in ctx_low:
            score += 2

        if score > best_score and score >= threshold_score:
            best_score = score
            best_num = num
            best_ctx = re.sub(r"\s+", " ", ctx).strip()

    if not best_num:
        return ExtractResult(value=None, evidence=None, score=0)

    return ExtractResult(value=f"{best_num} dias", evidence=best_ctx, score=int(best_score))
