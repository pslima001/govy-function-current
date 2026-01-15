# govy/extractors/pg001_pagamento.py
"""
PG001 - Extrator de Prazo de Pagamento

Este arquivo contém TODAS as regras para extração de prazo de pagamento.
Para editar regras, modifique as listas TERMOS_POSITIVOS e TERMOS_NEGATIVOS abaixo.

Última atualização: 15/01/2026
Responsável pela edição de regras: ChatGPT 5.2
Responsável pelo deploy: Claude
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExtractResult:
    """Resultado da extração de um parâmetro."""
    value: Optional[str]
    evidence: Optional[str]
    score: int


# =============================================================================
# CONFIGURAÇÃO DE REGRAS - EDITE AQUI
# =============================================================================

# Termos que AUMENTAM a pontuação (indicam contexto de prazo de pagamento)
TERMOS_POSITIVOS = [
    "pagamento",
    "pagar",
    "liquidação",
    "liquidacao",
    "liquidar",
    "quitação",
    "quitacao",
    "quitar",
    "nota fiscal",
    "nf",
    "fatura",
    "empenho",
    "atesto",
    "prazo de pagamento",
    "adimplemento",
    "crédito",
    "credito",
]

# Termos que DIMINUEM a pontuação (indicam outro tipo de prazo)
TERMOS_NEGATIVOS = [
    "entrega",
    "entregar",
    "fornecimento",
    "fornecer",
    "execução",
    "execucao",
    "vigência",
    "vigencia",
    "recurso",
    "impugna",
    "amostra",
    "proposta",
    "validade",
    "garantia",
    "prazo de entrega",
    "prazo de fornecimento",
    "execução do contrato",
    "execucao do contrato",
]

# Regex principal para capturar números seguidos de "dias"
REGEX_PRINCIPAL = r"(\d{1,3})\s*(?:\([^\)]{0,30}\))?\s*dias?\s*(?:úteis|uteis|corridos)?"

# Pontuação mínima para aceitar um candidato
THRESHOLD_SCORE = 2

# Pesos de pontuação
PESO_POSITIVO = 2    # Cada termo positivo encontrado adiciona este valor
PESO_NEGATIVO = 3    # Cada termo negativo encontrado subtrai este valor
BONUS_FRASE_TIPICA = 3  # Bônus para frases como "prazo de pagamento"

# =============================================================================
# FUNÇÕES DE EXTRAÇÃO - NÃO EDITE ABAIXO DESTA LINHA
# =============================================================================

def _normalizar_texto(s: str) -> str:
    """
    Normaliza texto para comparação:
    - converte para minúsculas
    - remove acentos (NFKD)
    """
    s = s.lower()
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) 
        if not unicodedata.combining(ch)
    )


def extract_pg001(text: str) -> ExtractResult:
    """
    Extrai prazo de pagamento do texto.
    
    Estratégia:
    1. Procura padrões de número + dias (úteis/corridos)
    2. Analisa contexto ao redor (±250 caracteres)
    3. Pontua baseado em termos positivos/negativos
    4. Retorna o candidato com maior pontuação
    
    Args:
        text: Texto completo do documento
        
    Returns:
        ExtractResult com valor, evidência e score
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    # Compilar regex
    padrao = re.compile(REGEX_PRINCIPAL, re.IGNORECASE)

    # Normalizar termos uma vez (para casar com texto com/sem acento)
    positivos_norm = [_normalizar_texto(p) for p in TERMOS_POSITIVOS]
    negativos_norm = [_normalizar_texto(n) for n in TERMOS_NEGATIVOS]

    best_num = None
    best_ctx = None
    best_score = -10

    for match in padrao.finditer(text):
        num = match.group(1)
        pos = match.start()
        
        # Extrair contexto (250 chars antes e depois)
        ctx_inicio = max(0, pos - 250)
        ctx_fim = min(len(text), pos + 250)
        ctx = text[ctx_inicio:ctx_fim]
        ctx_lower = ctx.lower()
        ctx_norm = _normalizar_texto(ctx)

        # Calcular pontuação
        score = 0
        
        # Somar pontos por termos positivos
        for termo in positivos_norm:
            if termo and termo in ctx_norm:
                score += PESO_POSITIVO
        
        # Subtrair pontos por termos negativos
        for termo in negativos_norm:
            if termo and termo in ctx_norm:
                score -= PESO_NEGATIVO

        # Bônus por frases típicas de prazo de pagamento
        if "prazo" in ctx_lower:
            if "pagamento" in ctx_lower or "liquidação" in ctx_lower or "liquidacao" in ctx_lower:
                score += BONUS_FRASE_TIPICA
        
        if "prazo de pagamento" in ctx_lower:
            score += 2

        # Atualizar melhor candidato
        if score > best_score and score >= THRESHOLD_SCORE:
            best_score = score
            best_num = num
            best_ctx = re.sub(r"\s+", " ", ctx).strip()

    if not best_num:
        return ExtractResult(value=None, evidence=None, score=0)

    return ExtractResult(
        value=f"{best_num} dias",
        evidence=best_ctx,
        score=int(best_score)
    )
