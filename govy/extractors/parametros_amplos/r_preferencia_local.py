"""
r_preferencia_local - Restricao/Preferencia por Local
=====================================================

Identifica se o edital estabelece restricao ou preferencia em razao do local.
IMPORTANTE: Nao confundir com criterio de desempate obrigatorio por lei.
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padroes de TABELA/PREAMBULO (prioridade maxima)
PATTERNS_TABELA_NAO = [
    r'prioridade\s+de\s+contrata[cç][aã]o[^.]{0,100}sediadas?\s+local[^.]{0,50}n[aã]o',
    r'prefer[eê]ncia\s+(?:por\s+)?local[^.]{0,30}n[aã]o',
    r'prefer[eê]ncia\s+local\s*[:\s]+n[aã]o',
    r'restri[cç][aã]o\s+local\s*[:\s]+n[aã]o',
]

PATTERNS_TABELA_SIM = [
    r'prioridade\s+de\s+contrata[cç][aã]o[^.]{0,100}sediadas?\s+local[^.]{0,50}sim',
    r'prefer[eê]ncia\s+(?:por\s+)?local[^.]{0,30}sim',
    r'prefer[eê]ncia\s+local\s*[:\s]+sim',
    r'restri[cç][aã]o\s+local\s*[:\s]+sim',
]

# Padroes que indicam SIM (ha preferencia/restricao local ESPECIFICA)
PATTERNS_SIM = [
    r'prefer[eê]ncia\s+para\s+empresas\s+(?:estabelecidas|sediadas)\s+no\s+munic[ií]pio',
    r'prioridade[^.]{0,50}(?:mei|me|epp)[^.]{0,50}sediadas?\s+local',
    r'(?:mei|me|epp)\s+sediadas?\s+local(?:mente)?',
    r'restri[cç][aã]o\s+(?:de\s+participa[cç][aã]o\s+)?(?:a\s+)?empresas\s+local',
    r'exclusiv(?:o|a|amente)\s+para\s+empresas\s+(?:do|da)\s+(?:munic[ií]pio|cidade|regi[aã]o)',
    r'somente\s+empresas\s+sediadas\s+(?:no|na)\s+(?:munic[ií]pio|cidade)',
]

# Padroes que indicam NAO
PATTERNS_NAO = [
    r'n[aã]o\s+(?:haver[aá]|h[aá])\s+(?:restri[cç][aã]o|prefer[eê]ncia)[^.]*local',
    r'sem\s+restri[cç][aã]o[^.]*local',
    r'independente(?:mente)?\s+(?:do|da)\s+localiza[cç][aã]o',
    r'aberta?\s+a\s+(?:todas\s+as\s+)?empresas',
    r'participa[cç][aã]o\s+(?:de\s+)?empresas\s+de\s+(?:todo|qualquer)',
]

# Padroes a IGNORAR (criterio de desempate obrigatorio por lei - nao e preferencia)
PATTERNS_IGNORAR = [
    r'crit[eé]rio\s+de\s+desempate[^.]*(?:estado|munic[ií]pio)',
    r'desempate[^.]*empresas\s+estabelecidas',
    r'(?:persistindo|permanecendo)\s+(?:o\s+)?empate[^.]*(?:estado|munic[ií]pio)',
    r'assegurada\s+prefer[eê]ncia[^.]*desempate',
]


def extract_r_preferencia_local(texto: str) -> RegexResult:
    """
    Identifica se ha preferencia/restricao por local.
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
            
            # Filtrar criterios de desempate (nao sao preferencia local real)
            is_desempate = any(re.search(p, contexto_lower) for p in PATTERNS_IGNORAR)
            
            if not is_desempate and not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                if 'n[aã]o' not in contexto_lower[:30]:
                    matches_sim.append({'contexto': contexto, 'pattern': pattern})

    if not matches_sim and not matches_nao:
        return result

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
        # Conflito - NAO vence (mais comum)
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

    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao)}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_preferencia_local(texto)
