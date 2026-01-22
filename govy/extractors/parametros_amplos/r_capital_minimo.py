"""
r_capital_minimo - Exige Capital/Patrimônio Mínimo
=================================================

Identifica se o edital exige capital social ou patrimônio líquido mínimo.

Padrões comuns:
- "capital mínimo ou patrimônio líquido mínimo de 10%"
- "capital social de no mínimo"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'capital\s+(?:social\s+)?m[íi]nimo[^.]*(\d+)\s*[%]',
    r'patrim[ôo]nio\s+l[íi]quido\s+m[íi]nimo[^.]*(\d+)\s*[%]',
    r'capital\s+(?:social\s+)?(?:ou\s+)?patrim[ôo]nio\s+l[íi]quido[^.]*m[íi]nimo',
    r'comprova[çc][ãa]o\s+de\s+(?:capital|patrim[ôo]nio)',
    r'capital\s+social\s+(?:integralizado\s+)?de\s+(?:no\s+)?m[íi]nimo',
    r'qualifica[çc][ãa]o\s+econ[ôo]mico[^.]*capital',
    r'(?:\d+)\s*[%][^.]*(?:capital|patrim[ôo]nio)',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]|haver[áa])\s+(?:exig[êe]ncia|exigid[oa])[^.]*(?:capital|patrim[ôo]nio)',
    r'dispensad[oa][^.]*(?:capital|patrim[ôo]nio)',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?(?:capital|patrim[ôo]nio)',
]

PATTERN_PERCENTUAL = r'(?:capital|patrim[ôo]nio)[^.]*?(\d+)\s*[%]'


def extract_r_capital_minimo(texto: str) -> RegexResult:
    """
    Identifica se exige capital/patrimônio mínimo.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO", e percentual se disponível
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    percentual = None
    
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
    
    # Busca percentual
    match_perc = re.search(PATTERN_PERCENTUAL, texto_lower)
    if match_perc:
        try:
            percentual = int(match_perc.group(1))
        except:
            pass
    
    if not matches_sim and not matches_nao:
        return result
    
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = f"SIM ({percentual}%)" if percentual else "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        if len(matches_sim) >= len(matches_nao):
            result.encontrado = True
            result.valor = f"SIM ({percentual}%)" if percentual else "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
    
    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao), 'percentual': percentual}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_capital_minimo(texto)
