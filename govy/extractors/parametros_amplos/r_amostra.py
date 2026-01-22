"""
r_amostra - Exige Amostra dos Produtos?
=======================================

Identifica se o edital exige apresentação de amostras.

Padrões comuns:
- "deverá apresentar amostras"
- "Exige Amostra? NÃO"
- "deixar de apresentar amostra" (como penalidade)
- "Fica dispensada... a apresentação de amostra"
- "Será exigida amostra dos produtos"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam SIM (exige amostra)
PATTERNS_SIM = [
    r'(?:dever[áa]|ser[áa]\s+exigid[oa])\s+apresentar\s+amostra',
    r'exig[êe]ncia\s+de\s+(?:apresenta[çc][ãa]o\s+de\s+)?amostra',
    r'apresentar\s+amostra[s]?\s+f[íi]sica',
    r'amostra[s]?\s+(?:ser[ãa]o|ser[áa])\s+exigida',
    r'necessita\s+de\s+amostra',
    r'exige\s+amostra[?]?\s*(?:sim|:)',
    r'ser[áa]\s+exigid[oa]\s+amostra',
    r'ser[ãa]o\s+exigid[oa]s\s+amostra',
    r'an[áa]lise\s+(?:t[ée]cnica\s+)?(?:referente\s+)?[àa]s?\s+amostra',
    r'poder[áa]\s+(?:ser\s+)?(?:realizada\s+)?(?:a\s+)?an[áa]lise\s+de\s+amostra',
]

# Padrões que indicam NÃO (não exige)
PATTERNS_NAO = [
    r'(?:fica\s+)?dispensad[oa][^.]*amostra',
    r'exige\s+amostra[?]?\s*n[ãa]o',
    r'n[ãa]o\s+(?:ser[áa]\s+)?exigid[oa]\s+amostra',
    r'sem\s+(?:necessidade\s+de\s+)?amostra',
    r'amostra[^.]*n[ãa]o\s+(?:ser[áa]\s+)?exigid',
]

# Padrões condicionais (pode ser exigido, mas não é obrigatório)
PATTERNS_CONDICIONAL = [
    r'poder[áa]\s+(?:ser\s+)?(?:solicita|exigi)',
    r'quando\s+exigid[oa]',
    r'caso\s+(?:o\s+)?termo\s+de\s+refer[êe]ncia\s+exija',
    r'(?:se|quando)\s+houver\s+d[úu]vida',
    r'poder[áa]\s+solicitar\s+amostra',
]


def extract_r_amostra(texto: str) -> RegexResult:
    """
    Identifica se o edital exige amostra dos produtos.
    
    Returns:
        RegexResult com valor "SIM", "NÃO" ou "CONDICIONAL"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    matches_condicional = []
    
    # Busca padrões de SIM
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_sim.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões de NÃO
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões CONDICIONAIS
    for pattern in PATTERNS_CONDICIONAL:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if 'amostra' in contexto.lower():
                if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                    matches_condicional.append({
                        'contexto': contexto,
                        'pattern': pattern
                    })
    
    if not matches_sim and not matches_nao and not matches_condicional:
        return result
    
    # Prioriza respostas definitivas
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    elif matches_condicional and not matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "CONDICIONAL"
        result.confianca = "media"
        result.evidencia = matches_condicional[0]['contexto']
    else:
        # Conflito ou condicional com outros
        if len(matches_sim) > len(matches_nao):
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        elif len(matches_nao) > len(matches_sim):
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "CONDICIONAL"
            result.confianca = "baixa"
            result.evidencia = matches_condicional[0]['contexto'] if matches_condicional else matches_sim[0]['contexto']
    
    result.detalhes = {
        'matches_sim': len(matches_sim),
        'matches_nao': len(matches_nao),
        'matches_condicional': len(matches_condicional)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_amostra(texto)
