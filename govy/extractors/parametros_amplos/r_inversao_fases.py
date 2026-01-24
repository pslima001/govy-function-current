"""
r_inversao_fases - Inversao das Fases de Julgamento/Habilitacao
===============================================================

Identifica se o edital estabelece a inversao das fases (habilitacao apos julgamento).
Na Lei 14.133, a regra e habilitacao DEPOIS do julgamento (inversao).
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padroes de TABELA/PREAMBULO (prioridade maxima)
PATTERNS_TABELA_SIM = [
    r'haver[aá]\s+invers[aã]o\s+(?:a\s+|da\s+)?fase\s+de\s+habilita[cç][aã]o\s*\??\s*sim',
    r'invers[aã]o\s+(?:das?\s+)?fases?\s*[:\s]+sim',
    r'invers[aã]o\s+das\s+fases\s*\??\s*sim',
    r'invers[aã]o\s*[:\s]+sim',
    r'fase\s+de\s+habilita[cç][aã]o\s+(?:poder[aá]\s+)?anteceder[^.]{0,30}sim',
]

PATTERNS_TABELA_NAO = [
    r'haver[aá]\s+invers[aã]o\s+(?:a\s+|da\s+)?fase\s+de\s+habilita[cç][aã]o\s*\??\s*n[aã]o',
    r'invers[aã]o\s+(?:das?\s+)?fases?\s*[:\s]+n[aã]o',
    r'invers[aã]o\s+das\s+fases\s*\??\s*n[aã]o',
    r'invers[aã]o\s*[:\s]+n[aã]o',
]

# Padroes que indicam SIM (habilitacao apos julgamento - padrao 14.133)
PATTERNS_SIM = [
    r'fase\s+de\s+habilita[cç][aã]o\s+(?:suceder[aá]|ocorrer[aá])\s+(?:as|às|a)\s+fase',
    r'fase\s+de\s+habilita[cç][aã]o\s+(?:suceder[aá]|ocorrer[aá])\s+ap[oó]s',
    r'habilita[cç][aã]o\s+ocorrer[aá]\s+ap[oó]s\s+(?:o\s+)?julgamento',
    r'ap[oó]s\s+(?:a\s+)?aceita[cç][aã]o\s+da\s+proposta[^.]*habilita[cç][aã]o',
    r'encerrad[oa]\s+(?:a\s+)?(?:an[aá]lise|fase)[^.]*(?:iniciar|inicia)[^.]*habilita[cç][aã]o',
    r'encerrad[oa]\s+(?:a\s+)?fase\s+de\s+(?:lances|julgamento)[^.]*habilita[cç][aã]o',
    r'habilita[cç][aã]o\s+(?:suceder[aá]|ocorrer[aá])[^.]*julgamento',
    r'pregoeiro[^.]*verificar[aá]\s+(?:a\s+)?habilita[cç][aã]o',
    r'fase\s+de\s+habilita[cç][aã]o[^.]*ap[oó]s[^.]*proposta',
    r'documentos\s+de\s+habilita[cç][aã]o\s+somente\s+ser[aã]o\s+exigidos[^.]*ap[oó]s',
    r'habilita[cç][aã]o\s+somente[^.]*licitante\s+mais\s+bem\s+classificad',
    r'fase\s+de\s+habilita[cç][aã]o\s+n[aã]o\s+anteceda',
]

# Padroes que indicam NAO (habilitacao antes do julgamento - modelo antigo)
PATTERNS_NAO = [
    r'habilita[cç][aã]o\s+(?:ocorrer[aá]|ser[aá])\s+antes',
    r'primeiro\s+(?:a\s+)?habilita[cç][aã]o',
    r'habilita[cç][aã]o\s+pr[eé]via',
    r'fase\s+de\s+habilita[cç][aã]o\s+anteceder[aá]',
    r'fase\s+de\s+habilita[cç][aã]o\s+anteceda\s+as\s+fases',
]


def extract_r_inversao_fases(texto: str) -> RegexResult:
    """
    Identifica se ha inversao das fases (habilitacao apos julgamento).
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()

    # 1. Primeiro verifica padroes de TABELA (prioridade maxima)
    for pattern in PATTERNS_TABELA_SIM:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    for pattern in PATTERNS_TABELA_NAO:
        match = re.search(pattern, texto_lower, re.IGNORECASE)
        if match:
            result.encontrado = True
            result.valor = "NAO"
            result.confianca = "alta"
            result.evidencia = extract_context(texto_norm, match)
            result.detalhes = {'fonte': 'tabela_preambulo', 'pattern': pattern}
            return result

    # 2. Busca padroes normais
    matches_sim = []
    matches_nao = []

    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_sim.append({'contexto': contexto, 'pattern': pattern})

    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({'contexto': contexto, 'pattern': pattern})

    if not matches_sim and not matches_nao:
        return result

    # Prioriza SIM (mais comum na 14.133)
    if matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    elif matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NAO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    else:
        # Conflito - mais matches vence
        if len(matches_sim) >= len(matches_nao):
            result.encontrado = True
            result.valor = "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NAO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']

    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao)}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_inversao_fases(texto)
