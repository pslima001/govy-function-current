"""
r_prorrogacao - Contrato Prorrogável
===================================

Identifica se o contrato é prorrogável.

Padrões comuns:
- "prorrogável por até 10 anos"
- "podendo ser prorrogado"
- "não admite prorrogação"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'prorrog[áa]vel',
    r'poder[áa]\s+ser\s+prorrogad[oa]',
    r'podendo\s+ser\s+prorrogad[oa]',
    r'admite\s+prorroga[çc][ãa]o',
    r'prorroga[çc][ãa]o[^.]*(?:at[ée]|por)\s+(?:\d+|um|dois|tr[êe]s|quatro|cinco|dez)\s+(?:anos?|meses)',
    r'prazo[^.]*prorrogad[oa]',
    r'vig[êe]ncia[^.]*prorrogad[oa]',
    r'renova[çc][ãa]o\s+(?:do\s+)?contrato',
    r'prorroga[çc][õo]es\s+sucessivas',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]\s+)?(?:admitid[oa]|permitid[oa])[^.]*prorroga[çc][ãa]o',
    r'n[ãa]o\s+(?:poder[áa]\s+ser\s+)?prorrogad[oa]',
    r'vedad[oa]\s+(?:a\s+)?prorroga[çc][ãa]o',
    r'sem\s+(?:possibilidade\s+de\s+)?prorroga[çc][ãa]o',
    r'improrrog[áa]vel',
]


def extract_r_prorrogacao(texto: str) -> RegexResult:
    """
    Identifica se o contrato é prorrogável.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({'contexto': contexto, 'pattern': pattern})
    
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            if not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                if 'não' not in contexto_lower[:30] and 'vedad' not in contexto_lower[:30]:
                    matches_sim.append({'contexto': contexto, 'pattern': pattern})
    
    if not matches_sim and not matches_nao:
        return result
    
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
    else:
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
    
    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao)}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_prorrogacao(texto)
