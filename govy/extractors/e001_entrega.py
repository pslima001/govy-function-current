# src/govy/extractors/e001_entrega.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int


def extract_e001(text: str) -> ExtractResult:
    """
    E001 — Prazo de Entrega
    Estratégia:
      - procurar padrões de "N dias" e pontuar pelo contexto (entrega, fornecimento, execução etc.)
      - evitar capturar prazos de pagamento/recurso/vigência etc.
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    padrao = re.compile(
        r'(\d{1,3})\s*(?:\([\w\sçãáéíóúõâêô.-]{0,25}\))?\s*dias?\s*(?:úteis|uteis|corridos)?',
        re.IGNORECASE
    )

    positivos = [
        "entrega", "entregar", "fornecimento", "fornecer", "execução", "execucao",
        "prestação", "prestacao", "serviço", "servico", "produto", "material",
        "objeto", "contrato", "adjudicado"
    ]
    negativos = [
        "pagamento", "pagar", "liquidação", "liquidacao", "nota fiscal", "nf",
        "fatura", "empenho", "atesto", "recurso", "impugna", "vigência", "vigencia",
        "validade", "garantia", "proposta"
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
        if "prazo" in ctx_low and ("entrega" in ctx_low or "fornecimento" in ctx_low):
            score += 3
        if "prazo de execução" in ctx_low or "prazo de fornecimento" in ctx_low:
            score += 2

        if score > best_score and score >= 2:
            best_score = score
            best_num = num
            best_ctx = re.sub(r"\s+", " ", ctx).strip()

    if not best_num:
        return ExtractResult(value=None, evidence=None, score=0)

    return ExtractResult(value=f"{best_num} dias", evidence=best_ctx, score=int(best_score))








