"""
r_escritorio_local - Exige Escritório na Cidade
================================================

Identifica se o edital exige que a empresa tenha escritório local.

Padrões comuns:
- "manter escritório na cidade"
- "instalar escritório no município"
- "sede ou filial no local"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam EXIGE
PATTERNS_SIM = [
    r'(?:manter|instalar|possuir)\s+(?:um\s+)?escrit[óo]rio\s+(?:na|no)\s+(?:cidade|munic[íi]pio|local)',
    r'escrit[óo]rio\s+(?:na|no)\s+(?:cidade|munic[íi]pio|local)',
    r'sede\s+(?:ou\s+filial\s+)?(?:na|no)\s+(?:cidade|munic[íi]pio|local)',
    r'filial\s+(?:na|no)\s+(?:cidade|munic[íi]pio|local)',
    r'representa[çc][ãa]o\s+(?:comercial\s+)?(?:na|no)\s+(?:cidade|munic[íi]pio|local)',
    r'dever[áa]\s+(?:manter|instalar|possuir)[^.]*escrit[óo]rio',
    r'obrigatoriedade\s+de\s+(?:manter|instalar)[^.]*escrit[óo]rio',
]

# Padrões que indicam NÃO EXIGE
PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]\s+)?exigid[oa]\s+(?:a\s+)?(?:manuten[çc][ãa]o\s+de\s+)?escrit[óo]rio',
    r'dispensad[oa]\s+(?:a\s+)?(?:exig[êe]ncia\s+de\s+)?escrit[óo]rio',
    r'independente\s+(?:de\s+)?(?:sede|escrit[óo]rio)\s+(?:na|no)',
]


def extract_r_escritorio_local(texto: str) -> RegexResult:
    """
    Identifica se exige escritório na cidade.
    
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
    return extract_r_escritorio_local(texto)
