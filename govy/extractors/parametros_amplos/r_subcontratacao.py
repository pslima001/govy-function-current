"""
r_subcontratacao - Permite Subcontratação?
==========================================

Identifica se o edital permite subcontratação do objeto.

Padrões comuns:
- "Não será admitida a subcontratação do objeto contratual"
- "Subcontratação vedada"
- "É admitida a subcontratação parcial do objeto"
- "vedada a subcontratação, total ou parcial"
- "ficando vedada a subcontratação"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam VEDADO/NÃO PERMITE
PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]\s+)?admitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'subcontrata[çc][ãa]o\s+vedad[oa]',
    r'vedad[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'n[ãa]o\s+(?:ser[áa]\s+)?permitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'[éeé]\s+vedad[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'ficando\s+vedad[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'n[ãa]o\s+subcontratar',
    r'n[ãa]o\s+(?:ser[áa]\s+)?permitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o\s+total\s+ou\s+parcial',
    r'vedad[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o[,]?\s+total\s+ou\s+parcial',
    r'n[ãa]o\s+ser[áa]\s+admitid[oa]\s+a\s+subcontrata[çc][ãa]o\s+do\s+objeto',
    r'contrato\s+n[ãa]o\s+poder[áa]\s+ser\s+objeto\s+de[^.]*subcontrata[çc][ãa]o',
    r'n[ãa]o\s+poder[áa]\s+ser\s+objeto\s+de[^.]*subcontrata[çc][ãa]o',
]

# Padrões que indicam PERMITIDO (total ou parcial)
PATTERNS_SIM = [
    r'[éeé]\s+admitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o\s+parcial',
    r'ser[áa]\s+admitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o\s+parcial',
    r'permitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o\s+parcial',
    r'subcontrata[çc][ãa]o\s+parcial\s+(?:[éeé]\s+)?permitid[oa]',
    r'admitid[oa]\s+(?:a\s+)?subcontrata[çc][ãa]o',
    r'poder[áa]\s+subcontratar',
]

# Padrões que indicam PARCIAL especificamente
PATTERNS_PARCIAL = [
    r'subcontrata[çc][ãa]o\s+parcial',
    r'parcialmente\s+subcontrat',
    r'subcontratar\s+(?:parcialmente|parte)',
]


def extract_r_subcontratacao(texto: str) -> RegexResult:
    """
    Identifica se o edital permite subcontratação.
    
    Returns:
        RegexResult com valor "SIM", "NÃO" ou "PARCIAL"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_nao = []
    matches_sim = []
    matches_parcial = []
    
    # Busca padrões de NÃO PERMITE
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões de PERMITE
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            if not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                # Verifica se não tem negação IMEDIATAMENTE ANTES do match (não em todo contexto)
                # Pega só 50 chars antes do match para verificar negação
                start_pos = match.start()
                texto_antes = texto_lower[max(0, start_pos-50):start_pos]
                
                # Só rejeita se a negação está próxima e relacionada
                has_negation = False
                if 'não será admitid' in texto_antes or 'não admitid' in texto_antes:
                    has_negation = True
                if 'vedad' in texto_antes:
                    has_negation = True
                    
                if not has_negation:
                    matches_sim.append({
                        'contexto': contexto,
                        'pattern': pattern
                    })
    
    # Busca padrões de PARCIAL
    for pattern in PATTERNS_PARCIAL:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                # Verifica se é "vedada parcial" ou "admitida parcial"
                if 'vedad' not in contexto.lower() and 'não' not in contexto.lower():
                    matches_parcial.append({
                        'contexto': contexto,
                        'pattern': pattern
                    })
    
    if not matches_nao and not matches_sim and not matches_parcial:
        return result
    
    # Prioriza NÃO (mais comum)
    if matches_nao and not matches_sim and not matches_parcial:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_parcial:
        result.encontrado = True
        result.valor = "PARCIAL"
        result.confianca = "alta" if len(matches_parcial) >= 2 else "media"
        result.evidencia = matches_parcial[0]['contexto']
    elif matches_sim:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "media"
        result.evidencia = matches_nao[0]['contexto']
    
    result.detalhes = {
        'matches_nao': len(matches_nao),
        'matches_sim': len(matches_sim),
        'matches_parcial': len(matches_parcial)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_subcontratacao(texto)
