# src/govy/extractors/pg001_pagamento.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int


def extract_pg001(text: str) -> ExtractResult:
    """
    PG001 — Prazo de Pagamento
    Estratégia:
      - procurar padrões de "N dias" e pontuar pelo contexto (pagamento, nota fiscal, fatura, liquidação etc.)
      - evitar capturar prazos de entrega/recurso/vigência etc.
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    padrao = re.compile(
        r'(\d{1,3})\s*(?:\([\w\sçãáéíóúõâêô.-]{0,25}\))?\s*dias?\s*(?:úteis|uteis|corridos)?',
        re.IGNORECASE
    )

    positivos = [
        "pagamento", "pagar", "liquidação", "liquidacao", "nota fiscal", "nf",
        "fatura", "empenho", "atesto", "liquidar"
    ]
    negativos = [
        "entrega", "fornecimento", "execução", "execucao", "vigência", "vigencia",
        "recurso", "impugna", "amostra", "proposta", "validade", "garantia"
    ]

    best_num = None
    best_ctx = None
    best_score = -10

    for m in padrao.finditer(text):
        num = m.group(1)
        pos = m.start()
        ctx = text[max(0, pos - 250): min(len(text), pos + 250)]
        ctx_low = ctx.lower()

        score = 0
        score += sum(2 for p in positivos if p in ctx_low)
        score -= sum(3 for n in negativos if n in ctx_low)

        # bônus por frases típicas
        if "prazo" in ctx_low and "pagamento" in ctx_low:
            score += 3
        if "nota fiscal" in ctx_low or "fatura" in ctx_low:
            score += 2

        if score > best_score and score >= 2:
            best_score = score
            best_num = num
            best_ctx = re.sub(r"\s+", " ", ctx).strip()

    if not best_num:
        return ExtractResult(value=None, evidence=None, score=0)

    return ExtractResult(value=f"{best_num} dias", evidence=best_ctx, score=int(best_score))

