"""
r_visita_tecnica - Exige Visita Tecnica?
========================================

Identifica se o edital exige visita tecnica obrigatoria.
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padroes de TABELA/PREAMBULO (prioridade maxima)
PATTERNS_TABELA_OBRIGATORIA = [
    r'exig[eê]ncia\s+de\s+visita\s+t[eé]cnica\s*[:\s]*sim',
    r'visita\s+t[eé]cnica\s*[:\s]+sim',
    r'visita\s+t[eé]cnica\s*[:\s]+obrigat[oó]ri',
    r'vistoria\s+t[eé]cnica\s*[:\s]*sim',
    r'vistoria\s*[:\s]+obrigat[oó]ri',
]

PATTERNS_TABELA_FACULTATIVA = [
    r'exig[eê]ncia\s+de\s+visita\s+t[eé]cnica\s*[:\s]*n[aã]o',
    r'visita\s+t[eé]cnica\s*[:\s]+n[aã]o',
    r'visita\s+t[eé]cnica\s*[:\s]+facultativ',
    r'vistoria\s+t[eé]cnica\s*[-–]\s*\(?facultativ',
    r'vistoria\s*[:\s]+facultativ',
    r'vistoria\s*[:\s]+n[aã]o',
]

# Padroes que indicam OBRIGATORIA
PATTERNS_OBRIGATORIA = [
    r'visita\s+t[eé]cnica\s+[eéè]\s+obrigat[oó]ri',
    r'vistoria\s+(?:t[eé]cnica\s+)?[eéè]\s+obrigat[oó]ri',
    r'vistoria\s+obrigat[oó]ri',
    r'dever[aã]o\s+efetuar\s+vistoria',
    r'obrigatoriedade\s+(?:de\s+)?(?:visita|vistoria)',
    r'(?:visita|vistoria)\s+t[eé]cnica\s+obrigat[oó]ri',
    r'obrigat[oó]ri[ao]\s+a\s+(?:realiza[cç][aã]o\s+(?:de|da)\s+)?(?:visita|vistoria)',
]

# Padroes que indicam FACULTATIVA
PATTERNS_FACULTATIVA = [
    r'visita\s+t[eé]cnica\s+[eéè]\s+faculta',
    r'vistoria\s+(?:t[eé]cnica\s+)?[eéè]\s+faculta',
    r'(?:visita|vistoria)\s+(?:t[eé]cnica\s+)?(?:\(?facultativ)',
    r'(?:visita|vistoria)\s+t[eé]cnica\s*[-–]\s*\(?facultativ',
    r'(?:as\s+)?licitantes\s+poder[aã]o\s+vistoriar',
    r'assegurad[oa]\s+(?:a\s+ele\s+)?o\s+direito\s+de\s+(?:realiza[cç][aã]o\s+de\s+)?vistoria',
    r'direito\s+de\s+realiza[cç][aã]o\s+de\s+vistoria\s+pr[eé]via',
    r'opte\s+por\s+n[aã]o\s+realizar\s+(?:a\s+)?vistoria',
    r'poder[aá]\s+substituir\s+(?:a\s+)?declara[cç][aã]o',
    r'vistoria\s+t[eé]cnica\s+poder[aá]\s+ser\s+realizada',
    r'caso\s+(?:a\s+)?licitante\s+n[aã]o\s+queira\s+realizar\s+(?:a\s+)?visita',
    r'poder[aá]\s+realizar\s+visita\s+t[eé]cnica',
    r'licitante\s+poder[aá]\s+realizar\s+visita',
]

# Padroes que indicam NAO EXIGE
PATTERNS_NAO = [
    r'vistoria[:\s]+n[aã]o',
    r'n[aã]o\s+(?:ser[aá]\s+)?exigid[oa]\s+(?:a\s+)?(?:visita|vistoria)',
    r'dispensad[oa]\s+(?:a\s+)?(?:exig[eê]ncia\s+de\s+)?(?:visita|vistoria)',
    r'sem\s+(?:necessidade\s+de\s+)?(?:visita|vistoria)',
]


def extract_r_visita_tecnica(texto: str) -> RegexResult:
    """
    Identifica se o edital exige visita tecnica.
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()

    # 1. Primeiro verifica padroes de TABELA (prioridade maxima)
    for pattern in PATTERNS_TABELA_OBRIGATORIA:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "OBRIGATORIA"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    for pattern in PATTERNS_TABELA_FACULTATIVA:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "FACULTATIVA"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    # 2. Busca padroes normais
    matches_obrigatoria = []
    matches_facultativa = []
    matches_nao = []

    for pattern in PATTERNS_OBRIGATORIA:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_obrigatoria.append({'contexto': contexto, 'pattern': pattern})

    for pattern in PATTERNS_FACULTATIVA:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_facultativa.append({'contexto': contexto, 'pattern': pattern})

    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({'contexto': contexto, 'pattern': pattern})

    if not matches_obrigatoria and not matches_facultativa and not matches_nao:
        return result

    # Prioriza respostas mais especificas
    if matches_obrigatoria and not matches_facultativa and not matches_nao:
        result.encontrado = True
        result.valor = "OBRIGATORIA"
        result.confianca = "alta" if len(matches_obrigatoria) >= 2 else "media"
        result.evidencia = matches_obrigatoria[0]['contexto']
    elif matches_facultativa and not matches_obrigatoria:
        result.encontrado = True
        result.valor = "FACULTATIVA"
        result.confianca = "alta" if len(matches_facultativa) >= 2 else "media"
        result.evidencia = matches_facultativa[0]['contexto']
    elif matches_nao and not matches_obrigatoria and not matches_facultativa:
        result.encontrado = True
        result.valor = "NAO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    else:
        # Conflito - prioriza facultativa (mais comum quando ha mencao)
        if matches_facultativa:
            result.encontrado = True
            result.valor = "FACULTATIVA"
            result.confianca = "baixa"
            result.evidencia = matches_facultativa[0]['contexto']
        elif matches_obrigatoria:
            result.encontrado = True
            result.valor = "OBRIGATORIA"
            result.confianca = "baixa"
            result.evidencia = matches_obrigatoria[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NAO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']

    result.detalhes = {
        'matches_obrigatoria': len(matches_obrigatoria),
        'matches_facultativa': len(matches_facultativa),
        'matches_nao': len(matches_nao)
    }

    return result


def extract(texto: str) -> RegexResult:
    return extract_r_visita_tecnica(texto)
