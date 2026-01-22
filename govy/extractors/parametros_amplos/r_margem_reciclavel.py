"""
r_margem_reciclavel - Margem para Reciclados/Biodegradáveis
==========================================================

Identifica se há margem de preferência para produtos reciclados/biodegradáveis.

Padrões comuns:
- "margem de preferência para produtos reciclados"
- "preferência para bens reciclados ou recicláveis"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'margem\s+de\s+prefer[êe]ncia[^.]*(?:reciclad|biodegrad[áa]vel|recicl[áa]vel)',
    r'prefer[êe]ncia[^.]*(?:produto|bem)[^.]*(?:reciclad|biodegrad[áa]vel|recicl[áa]vel)',
    r'(?:reciclad|biodegrad[áa]vel|recicl[áa]vel)[^.]*margem\s+de\s+prefer[êe]ncia',
    r'crit[ée]rio[^.]*(?:reciclad|biodegrad[áa]vel|recicl[áa]vel)',
    r'material\s+reciclad',
    r'produto[s]?\s+(?:at[óo]xico|biodegrad[áa]vel)',
    r'embalagens?[^.]*(?:reciclad|biodegrad[áa]vel)',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa]|ser[áa])[^.]*margem[^.]*(?:reciclad|biodegrad[áa]vel)',
    r'sem\s+(?:aplica[çc][ãa]o\s+de\s+)?margem[^.]*(?:reciclad|biodegrad[áa]vel)',
]


def extract_r_margem_reciclavel(texto: str) -> RegexResult:
    """
    Identifica se há margem para produtos reciclados/biodegradáveis.
    
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
                if 'não' not in contexto_lower[:30]:
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
    return extract_r_margem_reciclavel(texto)
