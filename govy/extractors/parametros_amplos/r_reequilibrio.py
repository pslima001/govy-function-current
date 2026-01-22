"""
r_reequilibrio - Previsão de Reequilíbrio Econômico-Financeiro
=============================================================

Identifica se o edital prevê reequilíbrio econômico-financeiro.

Padrões comuns:
- "reequilíbrio econômico-financeiro"
- "reajuste pelo IPCA"
- "revisão de preços"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'reequil[íi]brio\s+econ[ôo]mico[- ]?financeiro',
    r'revis[ãa]o\s+(?:de\s+)?pre[çc]os?',
    r'reajust(?:e|amento)\s+(?:de\s+)?pre[çc]os?',
    r'reajust(?:e|amento)\s+(?:pelo|com\s+base\s+(?:no|na))\s+(?:ipca|inpc|igp)',
    r'ipca[^.]*reajust',
    r'reajust[^.]*ipca',
    r'corre[çc][ãa]o\s+monet[áa]ria',
    r'atualiza[çc][ãa]o\s+(?:de\s+)?pre[çc]os?',
    r'repactua[çc][ãa]o',
    r'manuten[çc][ãa]o\s+do\s+equil[íi]brio',
    # Novos padrões para atualização monetária
    r'atualizad[oa]s?\s+monetariamente',
    r'aplica[çc][ãa]o\s+(?:do|de)\s+[íi]ndice',
    r'mediante\s+aplica[çc][ãa]o\s+(?:do\s+)?(?:ipca|inpc|igp|[íi]ndice)',
    r'[íi]ndice\s+(?:de\s+)?pre[çc]os[^.]*(?:consumidor|ipca)',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|h[áa]|caber[áa])\s+(?:reajust|reequil[íi]brio)',
    r'vedad[oa][^.]*reajust',
    r'sem\s+reajust(?:e|amento)',
    r'pre[çc]os?\s+(?:ser[ãa]o\s+)?fixos?',
    r'fixos?\s+e\s+irreajust[áa]ve(?:l|is)',  # "fixos e irreajustáveis"
    r'irreajust[áa]ve(?:l|is)',
]


def extract_r_reequilibrio(texto: str) -> RegexResult:
    """
    Identifica se prevê reequilíbrio econômico-financeiro.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO", e índice se disponível
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    indice = None
    
    # Detecta índice
    if 'ipca' in texto_lower:
        indice = 'IPCA'
    elif 'inpc' in texto_lower:
        indice = 'INPC'
    elif 'igp' in texto_lower:
        indice = 'IGP-M'
    
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
                if 'não' not in contexto_lower[:30] and 'vedad' not in contexto_lower[:30]:
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
        result.valor = f"SIM ({indice})" if indice else "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        if len(matches_sim) >= len(matches_nao):
            result.encontrado = True
            result.valor = f"SIM ({indice})" if indice else "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
    
    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao), 'indice': indice}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_reequilibrio(texto)
