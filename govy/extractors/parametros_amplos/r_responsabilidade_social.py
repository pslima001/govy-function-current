"""
r_responsabilidade_social - Política de Responsabilidade Social
==============================================================

Identifica se o edital exige política de responsabilidade social.

Padrões comuns:
- "responsabilidade social"
- "ação social"
- "inclusão social"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'responsabilidade\s+social',
    r'(?<!alter)a[çc][ãa]o\s+social',  # evita "alteração social"
    r'inclus[ãa]o\s+social',
    r'pol[íi]tica\s+(?:de\s+)?responsabilidade\s+social',
    r'programa\s+(?:de\s+)?responsabilidade\s+social',
    r'compromisso\s+social',
    r'impacto\s+social',
    r'benef[íi]cio\s+social',
    r'projeto[s]?\s+socia(?:l|is)',
    r'a[çc][õo]es\s+socia(?:l|is)',
]

# Contextos a evitar (não são sobre responsabilidade social corporativa)
CONTEXTO_NEGATIVO_ESPECIFICO = [
    'alteração social',
    'contrato social',
    'estatuto social',
    'razão social',
    'capital social',
    'previdência social',
    'seguridade social',
    'assistência social',
    'fiscal, social e trabalhista',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]|haver[áa])\s+(?:exigid[oa]|necess[áa]ri[oa])[^.]*responsabilidade\s+social',
    r'dispensad[oa][^.]*responsabilidade\s+social',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?responsabilidade\s+social',
]


def extract_r_responsabilidade_social(texto: str) -> RegexResult:
    """
    Identifica se exige política de responsabilidade social.
    
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
                # Verifica contextos negativos específicos
                if any(neg in contexto_lower for neg in CONTEXTO_NEGATIVO_ESPECIFICO):
                    continue
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
    return extract_r_responsabilidade_social(texto)
