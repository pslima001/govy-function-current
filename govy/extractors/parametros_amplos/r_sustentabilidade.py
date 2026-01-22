"""
r_sustentabilidade - Critérios de Sustentabilidade
=================================================

Identifica se o edital exige critérios de sustentabilidade ambiental.

Padrões comuns:
- "Guia Nacional de Contratações Sustentáveis"
- "critérios de sustentabilidade ambiental"
- "práticas sustentáveis"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'guia\s+nacional\s+de\s+contrata[çc][õo]es\s+sustent[áa]veis',
    r'crit[ée]rios?\s+de\s+sustentabilidade',
    r'sustentabilidade\s+ambiental',
    r'pr[áa]ticas?\s+sustent[áa]ve(?:l|is)',
    r'contrata[çc][ãa]o\s+sustent[áa]vel',
    r'desenvolvimento\s+sustent[áa]vel',
    r'impacto\s+ambiental',
    r'decreto\s+(?:n[º°]?\s*)?7\.?746',
    r'instru[çc][ãa]o\s+normativa[^.]*sustent[áa]vel',
    r'especifica[çc][õo]es\s+t[ée]cnicas[^.]*sustent[áa]ve',
    r'exig[êe]ncia[^.]*sustentabilidade',
    r'dever[áa][^.]*sustent[áa]ve',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa]|ser[áa])[^.]*crit[ée]rio[^.]*sustentabilidade',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?crit[ée]rio[^.]*sustentabilidade',
    r'dispensad[oa][^.]*sustentabilidade',
]


def extract_r_sustentabilidade(texto: str) -> RegexResult:
    """
    Identifica se exige critérios de sustentabilidade.
    
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
    return extract_r_sustentabilidade(texto)
