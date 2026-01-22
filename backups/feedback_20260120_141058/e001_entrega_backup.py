# govy/extractors/e001_entrega.py
"""
E001 - Extrator de Prazo de Entrega

Este arquivo contém TODAS as regras para extração de prazo de entrega.
Para editar regras, modifique as listas TERMOS_POSITIVOS e TERMOS_NEGATIVOS abaixo.

Última atualização: 16/01/2026
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

# Termos que AUMENTAM a pontuação (indicam contexto de prazo de entrega)
TERMOS_POSITIVOS = [
    "entrega",
    "entregar",
    "fornecimento",
    "fornecer",
    "execução",
    "execucao",
    "prestação",
    "prestacao",
    "serviço",
    "servico",
    "produto",
    "material",
    "objeto",
    "contrato",
    "adjudicado",
    "prazo de entrega",
    "prazo de fornecimento",
    "condições de entrega",
    "condicoes de entrega",
    # Termos de conclusão/realização
    "concluído",
    "concluido",
    "conclusão",
    "conclusao",
    "prazo de realização",
    "prazo de realizacao",
    "nota de empenho",
    "ordem de serviço",
    "ordem de servico",
    "autorização de fornecimento",
    "autorizacao de fornecimento",
    # Termos fortes de execução
    "deverão ser executados",
    "deverao ser executados",
    "serviços deverão",
    "servicos deverao",
    "em sua totalidade",
]

# Termos que DIMINUEM a pontuação (indicam outro tipo de prazo)
TERMOS_NEGATIVOS = [
    # Prazos de pagamento
    "pagamento",
    "pagar",
    "liquidação",
    "liquidacao",
    "nota fiscal",
    "nf",
    "fatura",
    "empenho",
    "atesto",
    # Prazos de recurso/impugnação
    "recurso",
    "impugna",
    # Prazos de vigência/validade
    "vigência",
    "vigencia",
    "validade",
    "prazo de validade",
    # Prazos de garantia
    "garantia",
    # Prazos de proposta
    "proposta",
    # Dotação orçamentária
    "dotação",
    "dotacao",
    "orçamentária",
    "orcamentaria",
    # Outros
    "vínculo",
    "vinculo",
    "catmat",
    "formulário",
    "formulario",
    "anexo ii",
    # Prazos de início de execução (não é prazo de entrega)
    "início da execução",
    "inicio da execucao",
    "início do objeto",
    "inicio do objeto",
    # Prazos de recebimento/fiscalização (administrativos)
    "recebimento definitivo",
    "recebimento provisório",
    "recebimento provisorio",
    "recebidos provisoriamente",
    "serão recebidos provisoriamente",
    "serao recebidos provisoriamente",
    "fiscalização técnica",
    "fiscalizacao tecnica",
    "fiscalização administrativa",
    "fiscalizacao administrativa",
    "aceitação mediante termo",
    "aceitacao mediante termo",
    "gestor do contrato",
    "fiscal técnico",
    "fiscal tecnico",
    "fiscal administrativo",
    "fiscais técnico",
    "fiscais tecnico",
    "mediante termos detalhados",
    "termos detalhados",
    # Câmara de modelos (ruído de template)
    "câmara nacional de modelos",
    "camara nacional de modelos",
    "consultoria-geral da união",
    "consultoria-geral da uniao",
]

# Regex principal para capturar números seguidos de "dias"
REGEX_PRINCIPAL = r"(\d{1,3})\s*(?:\([^\)]{0,30}\))?\s*dias?\s*(?:úteis|uteis|corridos)?"

# Pontuação mínima para aceitar um candidato
THRESHOLD_SCORE = 2

# Pesos de pontuação
PESO_POSITIVO = 2    # Cada termo positivo encontrado adiciona este valor
PESO_NEGATIVO = 3    # Cada termo negativo encontrado subtrai este valor
BONUS_FRASE_TIPICA = 3  # Bônus para frases como "prazo de entrega"

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


def extract_e001(text: str) -> ExtractResult:
    """
    Extrai prazo de entrega do texto.
    
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

        # Bônus por frases típicas de prazo de entrega
        if "prazo" in ctx_lower:
            if "entrega" in ctx_lower or "fornecimento" in ctx_lower:
                score += BONUS_FRASE_TIPICA
        
        if "prazo de execução" in ctx_lower or "prazo de execucao" in ctx_lower:
            score += 2
        if "prazo de fornecimento" in ctx_lower:
            score += 2
        if "prazo de entrega" in ctx_lower:
            score += 2
        if "prazo de realização" in ctx_lower or "prazo de realizacao" in ctx_lower:
            score += 2
        if "deverá ser concluído" in ctx_lower or "devera ser concluido" in ctx_lower:
            score += 3
        if "deverão ser executados" in ctx_lower or "deverao ser executados" in ctx_lower:
            score += 3
        if "em sua totalidade" in ctx_lower:
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