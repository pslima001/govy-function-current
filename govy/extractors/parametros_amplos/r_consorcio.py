"""
r_consorcio - Permite Consorcio?
================================

Identifica se o edital permite participacao de consorcios.
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padroes de TABELA/PREAMBULO (prioridade maxima)
PATTERNS_TABELA_NAO = [
    r'permite\s+(?:a\s+)?participa[cç][aã]o\s+(?:de\s+)?cons[oó]rcio\s*[:\s]*n[aã]o',
    r'participa[cç][aã]o\s+(?:de\s+)?cons[oó]rcio\s*[:\s]*n[aã]o',
    r'cons[oó]rcio\s*[:\s]+n[aã]o(?:\s+permit|$)',
    r'cons[oó]rcio\s*\??\s*n[aã]o\b',
]

PATTERNS_TABELA_SIM = [
    r'permite\s+(?:a\s+)?participa[cç][aã]o\s+(?:de\s+)?cons[oó]rcio\s*[:\s]*sim',
    r'participa[cç][aã]o\s+(?:de\s+)?cons[oó]rcio\s*[:\s]*sim',
    r'cons[oó]rcio\s*[:\s]+sim(?:\s|$)',
]

# Padroes que indicam VEDADO/NAO PERMITE
PATTERNS_NAO = [
    r'n[aã]o\s+ser[aá]\s+(?:admitid[oa]|permitid[oa])\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?(?:empresas\s+(?:em\s+)?(?:regime\s+de\s+)?)?cons[oó]rcio',
    r'n[aã]o\s+ser[aá]\s+permitid[oa]\s+(?:a\s+)?participa[cç][aã]o\s+de\s+empresas\s+em\s+(?:regime\s+de\s+)?cons[oó]rcio',
    r'vedad[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'[eéè]\s+vedad[oa]\s+(?:o\s+)?cons[oó]rcio',
    r'n[aã]o\s+(?:ser[aá]\s+)?permitid[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'n[aã]o\s+poder[aã]o\s+participar[^.]{0,50}cons[oó]rcio',
    r'pessoas\s+jur[ií]dicas\s+reunidas\s+em\s+cons[oó]rcio',
]

# Padroes que indicam PERMITIDO
PATTERNS_SIM = [
    r'(?<!n[aã]o\s)ser[aá]\s+permitid[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'[eéè]\s+permitid[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'cons[oó]rcio\s+(?:de\s+empresas\s+)?permitid[oa]',
    r'admitid[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'ser[aá]\s+admitid[oa]\s+(?:a\s+participa[cç][aã]o\s+de\s+empresas\s+em\s+)?cons[oó]rcio',
]

# Padroes CONDICIONAIS (nao contam como SIM)
PATTERNS_CONDICIONAL = [
    r'quando\s+permitid[oa]\s+(?:a\s+participa[cç][aã]o\s+(?:de|em)\s+)?cons[oó]rcio',
    r'caso\s+(?:seja\s+)?permitid[oa]\s+cons[oó]rcio',
    r'se\s+(?:for\s+)?permitid[oa]\s+cons[oó]rcio',
]


def extract_r_consorcio(texto: str) -> RegexResult:
    """
    Identifica se o edital permite consorcio.
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()

    # 1. Primeiro verifica padroes de TABELA (prioridade maxima)
    for pattern in PATTERNS_TABELA_NAO:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "NAO"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    for pattern in PATTERNS_TABELA_SIM:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    # 2. Busca padroes normais
    matches_nao = []
    matches_sim = []

    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({'contexto': contexto, 'pattern': pattern})

    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            # Filtrar condicionais
            is_condicional = any(re.search(p, contexto_lower) for p in PATTERNS_CONDICIONAL)
            if not is_condicional and not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_sim.append({'contexto': contexto, 'pattern': pattern})

    if not matches_nao and not matches_sim:
        return result

    # Prioriza NAO (mais comum em editais)
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NAO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        # Conflito - NAO vence por ser mais comum
        if len(matches_nao) >= len(matches_sim):
            result.encontrado = True
            result.valor = "NAO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']

    result.detalhes = {'matches_nao': len(matches_nao), 'matches_sim': len(matches_sim)}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_consorcio(texto)
