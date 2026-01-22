"""
r_preferencia_local - Restrição/Preferência por Local
=====================================================

Identifica se o edital estabelece restrição ou preferência em razão do local.

Padrões comuns:
- "empresas estabelecidas no território do Estado"
- "preferência para empresas estabelecidas no Município"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam SIM (há preferência/restrição local)
PATTERNS_SIM = [
    r'empresas\s+estabelecidas\s+no\s+(?:territ[óo]rio\s+(?:do|da)\s+)?(?:estado|munic[íi]pio|distrito)',
    r'prefer[êe]ncia[^.]*empresas\s+estabelecidas\s+no\s+(?:estado|munic[íi]pio)',
    r'prefer[êe]ncia[^.]*(?:estado|munic[íi]pio|local)',
    r'estabelecid[oa]s?\s+no\s+munic[íi]pio',
    r'sediadas?\s+no\s+(?:estado|munic[íi]pio)',
    r'sede\s+(?:no|na)\s+(?:cidade|munic[íi]pio|estado)',
    r'restri[çc][ãa]o[^.]*local',
    r'crit[ée]rio\s+de\s+desempate[^.]*(?:estado|munic[íi]pio|local)',
]

# Padrões que indicam NÃO
PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa])\s+(?:restri[çc][ãa]o|prefer[êe]ncia)[^.]*local',
    r'sem\s+restri[çc][ãa]o[^.]*local',
    r'independente(?:mente)?\s+(?:do|da)\s+localiza[çc][ãa]o',
]


def extract_r_preferencia_local(texto: str) -> RegexResult:
    """
    Identifica se há preferência/restrição por local.
    
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
    return extract_r_preferencia_local(texto)
