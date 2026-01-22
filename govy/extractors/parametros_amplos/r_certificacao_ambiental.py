"""
r_certificacao_ambiental - Exige Certificações Ambientais
========================================================

Identifica se o edital exige certificações ambientais.

Padrões comuns:
- "certificação ISO 14001"
- "licença ambiental"
- "certificação ambiental"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'certifica[çc][ãa]o\s+(?:ambiental|iso\s*14)',
    r'iso\s*14\.?001',
    r'licen[çc]a\s+ambiental',
    r'licenciamento\s+ambiental',
    r'selo\s+(?:verde|ambiental|ecol[óo]gico)',
    r'certifica[çc][ãa]o\s+(?:de\s+)?gest[ãa]o\s+ambiental',
    r'sistema\s+de\s+gest[ãa]o\s+ambiental',
    r'norma[s]?\s+ambienta(?:l|is)',
    r'cadastro\s+t[ée]cnico\s+federal',
    r'ibama',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]|haver[áa])\s+(?:exigid[oa]|necess[áa]ri[oa])[^.]*certifica[çc][ãa]o\s+ambiental',
    r'dispensad[oa][^.]*certifica[çc][ãa]o\s+ambiental',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?certifica[çc][ãa]o\s+ambiental',
]


def extract_r_certificacao_ambiental(texto: str) -> RegexResult:
    """
    Identifica se exige certificações ambientais.
    
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
    return extract_r_certificacao_ambiental(texto)
