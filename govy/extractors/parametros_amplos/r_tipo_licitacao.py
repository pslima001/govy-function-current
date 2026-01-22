"""
r_tipo_licitacao - Licitação por Item ou Lote
=============================================

Identifica se a licitação é por ITEM ou LOTE.

Padrões comuns:
- "A licitação será dividida por itens"
- "licitação será realizada em grupo único"
- "contratação será dividida em itens"
- "adjudicação por itens"
- "licitação será realizada por item"
- "A presente contratação será constituída de 4 lotes"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam ITEM
PATTERNS_ITEM = [
    r'licita[çc][ãa]o\s+(?:ser[áa]|será)\s+(?:dividida|realizada)\s+por\s+ite(?:m|ns)',
    r'contrata[çc][ãa]o\s+(?:ser[áa]|será)\s+(?:dividida|realizada)\s+(?:por|em)\s+ite(?:m|ns)',
    r'contrata[çc][ãa]o\s+ser[áa]\s+dividida\s+em\s+itens',
    r'adjudica[çc][ãa]o\s+por\s+ite(?:m|ns)',
    r'licita[çc][ãa]o\s+dividida\s+por\s+item',
    r'licita[çc][ãa]o\s+ser[áa]\s+por\s+item',
    r'por\s+valor\s+unit[áa]rio',
    r'ser[áa]\s+por\s+valor\s+unit[áa]rio',
    r'itens\s+individual(?:izados)?',
    r'contrata[çc][ãa]o\s+por\s+item',
    r'dividida\s+em\s+itens',  # Adicionado
    r'ser[áa]\s+dividida\s+em\s+itens',  # Adicionado
]

# Padrões que indicam LOTE
PATTERNS_LOTE = [
    r'licita[çc][ãa]o\s+(?:ser[áa]|será)\s+realizada\s+em\s+(?:grupo|lote)\s+[úu]nico',
    r'licita[çc][ãa]o\s+(?:ser[áa]|será)\s+realizada\s+em\s+(?:\d+|um|dois|três|quatro|cinco)\s+lotes?',
    r'constitu[íi]da\s+de\s+(?:\d+|um|dois|três|quatro|cinco)\s+lotes?',
    r'dividida\s+em\s+(?:\d+|um|dois|três|quatro|cinco)\s+lotes?',
    r'aquisição\s+(?:ser[áa]|será)\s+dividida\s+em\s+(?:\d+|um|dois|três|quatro|cinco)\s+lotes?',
    r'em\s+(?:único|unico)\s+lote',
    r'grupo\s+[úu]nico',
    r'lote\s+[úu]nico',
    r'menor\s+pre[çc]o\s+global',
    r'pre[çc]o\s+global',
]


def extract_r_tipo_licitacao(texto: str) -> RegexResult:
    """
    Identifica se a licitação é por ITEM ou LOTE.
    
    Returns:
        RegexResult com valor "ITEM" ou "LOTE"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_item = []
    matches_lote = []
    
    # Busca padrões de ITEM
    for pattern in PATTERNS_ITEM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            # Verifica se não é sumário
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_item.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões de LOTE
    for pattern in PATTERNS_LOTE:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            # Verifica se não é sumário
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_lote.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Decide baseado em qual tem mais matches ou qual aparece primeiro
    if not matches_item and not matches_lote:
        return result
    
    # Se só tem um tipo de match
    if matches_item and not matches_lote:
        result.encontrado = True
        result.valor = "ITEM"
        result.confianca = "alta" if len(matches_item) >= 2 else "media"
        result.evidencia = matches_item[0]['contexto']
        result.detalhes = {'matches_item': len(matches_item), 'matches_lote': 0}
        return result
    
    if matches_lote and not matches_item:
        result.encontrado = True
        result.valor = "LOTE"
        result.confianca = "alta" if len(matches_lote) >= 2 else "media"
        result.evidencia = matches_lote[0]['contexto']
        result.detalhes = {'matches_item': 0, 'matches_lote': len(matches_lote)}
        return result
    
    # Se tem ambos, usa o que tem mais matches
    if len(matches_item) > len(matches_lote):
        result.encontrado = True
        result.valor = "ITEM"
        result.confianca = "media"  # Conflito = confiança média
        result.evidencia = matches_item[0]['contexto']
    elif len(matches_lote) > len(matches_item):
        result.encontrado = True
        result.valor = "LOTE"
        result.confianca = "media"
        result.evidencia = matches_lote[0]['contexto']
    else:
        # Empate - confiança baixa
        result.encontrado = True
        result.valor = "ITEM"  # Default para item em caso de empate
        result.confianca = "baixa"
        result.evidencia = matches_item[0]['contexto']
    
    result.detalhes = {
        'matches_item': len(matches_item),
        'matches_lote': len(matches_lote)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_tipo_licitacao(texto)
