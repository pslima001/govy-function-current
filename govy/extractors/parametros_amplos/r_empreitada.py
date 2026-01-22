"""
r_empreitada - Modalidade de Empreitada
=======================================

Identifica a modalidade de empreitada (obras/engenharia).

Tipos:
- PREÇO GLOBAL: Preço certo e total
- PREÇO UNITÁRIO: Execução por unidade de medida
- INTEGRAL: Empreitada por preço global integral
- TAREFA: Para mão de obra
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_GLOBAL = [
    r'empreitada\s+(?:por\s+)?pre[çc]o\s+global',
    r'pre[çc]o\s+global\s+(?:de\s+empreitada)?',
    r'regime\s+de\s+(?:execu[çc][ãa]o\s+)?(?:por\s+)?empreitada\s+(?:por\s+)?pre[çc]o\s+global',
    r'empreitada\s+integral',
    r'contrata[çc][ãa]o\s+(?:por\s+)?pre[çc]o\s+global',
    # Novos patterns para licitação por menor preço global
    r'menor\s+pre[çc]o\s+global',
    r'tipo\s+menor\s+pre[çc]o\s+global',
    r'crit[ée]rio\s+(?:de\s+)?(?:julgamento\s+)?(?:por\s+)?menor\s+pre[çc]o\s+global',
]

PATTERNS_UNITARIO = [
    r'empreitada\s+(?:por\s+)?pre[çc]o\s+unit[áa]rio',
    r'pre[çc]o\s+unit[áa]rio\s+(?:de\s+empreitada)?',
    r'regime\s+de\s+(?:execu[çc][ãa]o\s+)?(?:por\s+)?empreitada\s+(?:por\s+)?pre[çc]o\s+unit[áa]rio',
    r'contrata[çc][ãa]o\s+(?:por\s+)?pre[çc]o\s+unit[áa]rio',
    r'unidade\s+de\s+medida',
]

PATTERNS_TAREFA = [
    r'empreitada\s+(?:por\s+)?tarefa',
    r'regime\s+de\s+(?:execu[çc][ãa]o\s+)?tarefa',
]


def extract_r_empreitada(texto: str) -> RegexResult:
    """
    Identifica a modalidade de empreitada.
    
    Returns:
        RegexResult com valor "PREÇO GLOBAL", "PREÇO UNITÁRIO", "TAREFA" ou "INTEGRAL"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_global = []
    matches_unitario = []
    matches_tarefa = []
    
    for pattern in PATTERNS_GLOBAL:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_global.append({'contexto': contexto, 'pattern': pattern})
    
    for pattern in PATTERNS_UNITARIO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_unitario.append({'contexto': contexto, 'pattern': pattern})
    
    for pattern in PATTERNS_TAREFA:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_tarefa.append({'contexto': contexto, 'pattern': pattern})
    
    if not matches_global and not matches_unitario and not matches_tarefa:
        return result
    
    # Determina a modalidade com mais matches
    if len(matches_global) >= len(matches_unitario) and len(matches_global) >= len(matches_tarefa) and matches_global:
        result.encontrado = True
        result.valor = "PREÇO GLOBAL"
        result.confianca = "alta" if len(matches_global) >= 2 else "media"
        result.evidencia = matches_global[0]['contexto']
    elif len(matches_unitario) >= len(matches_tarefa) and matches_unitario:
        result.encontrado = True
        result.valor = "PREÇO UNITÁRIO"
        result.confianca = "alta" if len(matches_unitario) >= 2 else "media"
        result.evidencia = matches_unitario[0]['contexto']
    elif matches_tarefa:
        result.encontrado = True
        result.valor = "TAREFA"
        result.confianca = "alta" if len(matches_tarefa) >= 2 else "media"
        result.evidencia = matches_tarefa[0]['contexto']
    
    result.detalhes = {
        'matches_global': len(matches_global),
        'matches_unitario': len(matches_unitario),
        'matches_tarefa': len(matches_tarefa)
    }
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_empreitada(texto)
