"""
r_inversao_fases - Inversão das Fases de Julgamento/Habilitação
===============================================================

Identifica se o edital estabelece a inversão das fases (habilitação após julgamento).
Na Lei 14.133, a regra é habilitação DEPOIS do julgamento (inversão).

Padrões comuns:
- "a fase de habilitação sucederá as fases de apresentação de propostas e lances e de julgamento"
- "A fase de habilitação ocorrerá após o julgamento das propostas"
- "Encerrada a análise quanto à aceitação da proposta, se iniciará a fase de habilitação"
- "Habilitação ocorrerá após julgamento das propostas"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam SIM (habilitação após julgamento - padrão 14.133)
PATTERNS_SIM = [
    r'fase\s+de\s+habilita[çc][ãa]o\s+(?:suceder[áa]|ocorrer[áa])\s+(?:as|às|a)\s+fase',
    r'fase\s+de\s+habilita[çc][ãa]o\s+(?:suceder[áa]|ocorrer[áa])\s+ap[óo]s',
    r'habilita[çc][ãa]o\s+ocorrer[áa]\s+ap[óo]s\s+(?:o\s+)?julgamento',
    r'ap[óo]s\s+(?:a\s+)?aceita[çc][ãa]o\s+da\s+proposta[^.]*habilita[çc][ãa]o',
    r'encerrad[oa]\s+(?:a\s+)?(?:an[áa]lise|fase)[^.]*(?:iniciar|inicia)[^.]*habilita[çc][ãa]o',
    r'encerrad[oa]\s+(?:a\s+)?fase\s+de\s+(?:lances|julgamento)[^.]*habilita[çc][ãa]o',
    r'habilita[çc][ãa]o\s+(?:suceder[áa]|ocorrer[áa])[^.]*julgamento',
    r'pregoeiro[^.]*verificar[áa]\s+(?:a\s+)?habilita[çc][ãa]o',
    r'fase\s+de\s+habilita[çc][ãa]o[^.]*ap[óo]s[^.]*proposta',
]

# Padrões que indicam NÃO (habilitação antes do julgamento - modelo antigo)
PATTERNS_NAO = [
    r'habilita[çc][ãa]o\s+(?:ocorrer[áa]|ser[áa])\s+antes',
    r'primeiro\s+(?:a\s+)?habilita[çc][ãa]o',
    r'habilita[çc][ãa]o\s+pr[ée]via',
    r'fase\s+de\s+habilita[çc][ãa]o\s+anteceder[áa]',
]


def extract_r_inversao_fases(texto: str) -> RegexResult:
    """
    Identifica se há inversão das fases (habilitação após julgamento).
    
    Na Lei 14.133/2021, o padrão é a inversão (habilitação depois).
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    
    # Busca padrões de SIM (inversão - habilitação após)
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_sim.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões de NÃO (sem inversão)
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    if not matches_sim and not matches_nao:
        return result
    
    # Prioriza SIM (mais comum na 14.133)
    if matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    elif matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    else:
        # Conflito - mais matches vence
        if len(matches_sim) >= len(matches_nao):
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
    
    result.detalhes = {
        'matches_sim': len(matches_sim),
        'matches_nao': len(matches_nao)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_inversao_fases(texto)
