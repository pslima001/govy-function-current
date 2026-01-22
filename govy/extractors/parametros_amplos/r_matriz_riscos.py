"""
r_matriz_riscos - Há Matriz de Riscos?
=====================================

Identifica se o edital contém matriz de riscos.

Padrões comuns:
- "matriz de riscos"
- "alocação de riscos"
- "Anexo X - Matriz de Riscos"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'matriz\s+de\s+riscos?',
    r'aloca[çc][ãa]o\s+de\s+riscos?',
    r'distribui[çc][ãa]o\s+de\s+riscos?',
    r'gest[ãa]o\s+de\s+riscos?',
    r'anexo[^.]*matriz\s+de\s+riscos?',
    r'riscos?\s+e\s+responsabilidades',
    r'art(?:igo)?\.?\s*103[^.]*matriz',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa]|cont[ée]m)\s+matriz\s+de\s+riscos?',
    r'dispensad[oa][^.]*matriz\s+de\s+riscos?',
    r'sem\s+matriz\s+de\s+riscos?',
]


def extract_r_matriz_riscos(texto: str) -> RegexResult:
    """
    Identifica se há matriz de riscos.
    
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
                if 'não' not in contexto_lower[:30] and 'dispensad' not in contexto_lower[:30]:
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
    return extract_r_matriz_riscos(texto)
