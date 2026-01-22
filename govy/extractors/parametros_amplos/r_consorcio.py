"""
r_consorcio - Permite Consórcio?
================================

Identifica se o edital permite participação de consórcios.

Padrões comuns:
- "Não será admitido consórcio"
- "vedada a participação em consórcio"
- "pessoas jurídicas reunidas em consórcio" (vedação)
- "É vedado o consórcio entre empresas"
- "Será permitida a participação de pessoas jurídicas organizadas em consórcio"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam VEDADO/NÃO PERMITE
PATTERNS_NAO = [
    r'n[ãa]o\s+ser[áa]\s+(?:admitid[oa]|permitid[oa])\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?(?:empresas\s+(?:em\s+)?(?:regime\s+de\s+)?)?cons[óo]rcio',
    r'n[ãa]o\s+ser[áa]\s+permitid[oa]\s+(?:a\s+)?participa[çc][ãa]o\s+de\s+empresas\s+em\s+(?:regime\s+de\s+)?cons[óo]rcio',
    r'vedad[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'[éeé]\s+vedad[oa]\s+(?:o\s+)?cons[óo]rcio',
    r'cons[óo]rcio\s+(?:n[ãa]o\s+)?(?:permitid[oa]|proibid[oa]|vedad[oa])',
    r'n[ãa]o\s+(?:ser[áa]\s+)?permitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'n[ãa]o\s+poder[ãa]o\s+participar[^.]*cons[óo]rcio',
    r'pessoas\s+jur[íi]dicas\s+reunidas\s+em\s+cons[óo]rcio',  # geralmente em lista de vedações
    r'empresas\s+reunidas\s+em\s+cons[óo]rcio[^.]*vedad',
    r'participa[çc][ãa]o\s+de\s+empresas\s+em\s+(?:regime\s+de\s+)?cons[óo]rcio[^.]*n[ãa]o',
    r'empresa[^.]*isoladamente\s+ou\s+em\s+cons[óo]rcio[^.]*(?:n[ãa]o\s+poder|respons[áa]vel)',
]

# Padrões que indicam PERMITIDO
PATTERNS_SIM = [
    r'(?<!n[ãa]o\s)ser[áa]\s+permitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'[éeé]\s+permitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'quando\s+permitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'cons[óo]rcio\s+(?:de\s+empresas\s+)?permitid[oa]',
    r'admitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+(?:de|em)\s+)?cons[óo]rcio',
    r'ser[áa]\s+admitid[oa]\s+(?:a\s+participa[çc][ãa]o\s+de\s+empresas\s+em\s+)?cons[óo]rcio',
]


def extract_r_consorcio(texto: str) -> RegexResult:
    """
    Identifica se o edital permite consórcio.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_nao = []
    matches_sim = []
    
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
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_sim.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    if not matches_nao and not matches_sim:
        return result
    
    # Prioriza NÃO (mais comum em editais)
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
        result.detalhes = {'matches_nao': len(matches_nao), 'matches_sim': len(matches_sim)}
        return result
    
    if matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
        result.detalhes = {'matches_nao': len(matches_nao), 'matches_sim': len(matches_sim)}
        return result
    
    # Se tem ambos, confiança baixa - precisa IA
    if len(matches_nao) > len(matches_sim):
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "baixa"
        result.evidencia = matches_nao[0]['contexto']
    else:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "baixa"
        result.evidencia = matches_sim[0]['contexto']
    
    result.detalhes = {
        'matches_nao': len(matches_nao),
        'matches_sim': len(matches_sim)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_consorcio(texto)
