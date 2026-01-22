"""
r_prova_conceito - Exige Prova de Conceito (POC)
================================================

Identifica se o edital exige prova de conceito.

Padrões comuns:
- "prova de conceito"
- "POC"
- "demonstração de funcionamento"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'prova\s+de\s+conceito',
    r'\bpoc\b',
    r'demonstra[çc][ãa]o\s+(?:de\s+)?(?:funcionamento|t[ée]cnica|do\s+produto|do\s+sistema)',
    r'teste\s+(?:de\s+)?(?:funcionamento|t[ée]cnico|pr[áa]tico)',
    r'avalia[çc][ãa]o\s+(?:de\s+)?(?:funcionamento|t[ée]cnica\s+do\s+produto)',
    r'valida[çc][ãa]o\s+t[ée]cnica\s+(?:do\s+)?produto',
    r'homologa[çc][ãa]o\s+(?:de\s+)?(?:amostra|produto)',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa]|ser[áa])\s+(?:exig[êe]ncia\s+de\s+)?prova\s+de\s+conceito',
    r'dispensad[oa]\s+(?:a\s+)?prova\s+de\s+conceito',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?prova\s+de\s+conceito',
]


def extract_r_prova_conceito(texto: str) -> RegexResult:
    """
    Identifica se exige prova de conceito.
    
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
    return extract_r_prova_conceito(texto)
