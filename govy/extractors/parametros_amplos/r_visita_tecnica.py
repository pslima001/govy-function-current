"""
r_visita_tecnica - Exige Visita Técnica?
========================================

Identifica se o edital exige visita técnica obrigatória.

Padrões comuns:
- "A visita técnica é obrigatória"
- "A visita técnica é facultada aos licitantes"
- "Vistoria: NÃO"
- "poderá substituir a declaração exigida... por declaração formal"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam OBRIGATÓRIA
PATTERNS_OBRIGATORIA = [
    r'visita\s+t[ée]cnica\s+[éeè]\s+obrigat[óo]ri',
    r'vistoria\s+(?:t[ée]cnica\s+)?[éeè]\s+obrigat[óo]ri',
    r'vistoria\s+obrigat[óo]ri',
    r'dever[ãa]o\s+efetuar\s+vistoria',
    r'obrigatoriedade\s+(?:de\s+)?(?:visita|vistoria)',
    r'(?:visita|vistoria)\s+t[ée]cnica\s+obrigat[óo]ri',
]

# Padrões que indicam FACULTATIVA
PATTERNS_FACULTATIVA = [
    r'visita\s+t[ée]cnica\s+[éeè]\s+faculta',
    r'vistoria\s+(?:t[ée]cnica\s+)?[éeè]\s+faculta',
    r'(?:visita|vistoria)\s+(?:t[ée]cnica\s+)?(?:\(?facultativ)',
    r'(?:visita|vistoria)\s+t[ée]cnica\s*[-–]\s*\(?facultativ',  # NOVO: "VISTORIA TÉCNICA - (FACULTATIVA)"
    r'(?:as\s+)?licitantes\s+poder[ãa]o\s+vistoriar',
    r'assegurad[oa]\s+(?:a\s+ele\s+)?o\s+direito\s+de\s+(?:realiza[çc][ãa]o\s+de\s+)?vistoria',
    r'direito\s+de\s+realiza[çc][ãa]o\s+de\s+vistoria\s+pr[ée]via',
    r'opte\s+por\s+n[ãa]o\s+realizar\s+(?:a\s+)?vistoria',
    r'poder[áa]\s+substituir\s+(?:a\s+)?declara[çc][ãa]o',
    r'vistoria\s+t[ée]cnica\s+poder[áa]\s+ser\s+realizada',  # NOVO
]

# Padrões que indicam NÃO EXIGE
PATTERNS_NAO = [
    r'vistoria[:\s]+n[ãa]o',
    r'n[ãa]o\s+(?:ser[áa]\s+)?exigid[oa]\s+(?:a\s+)?(?:visita|vistoria)',
    r'dispensad[oa]\s+(?:a\s+)?(?:exig[êe]ncia\s+de\s+)?(?:visita|vistoria)',
    r'sem\s+(?:necessidade\s+de\s+)?(?:visita|vistoria)',
]


def extract_r_visita_tecnica(texto: str) -> RegexResult:
    """
    Identifica se o edital exige visita técnica.
    
    Returns:
        RegexResult com valor "OBRIGATÓRIA", "FACULTATIVA" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_obrigatoria = []
    matches_facultativa = []
    matches_nao = []
    
    # Busca padrões OBRIGATÓRIA
    for pattern in PATTERNS_OBRIGATORIA:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_obrigatoria.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões FACULTATIVA
    for pattern in PATTERNS_FACULTATIVA:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_facultativa.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões NÃO
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    if not matches_obrigatoria and not matches_facultativa and not matches_nao:
        return result
    
    # Prioriza respostas mais específicas
    if matches_obrigatoria and not matches_facultativa and not matches_nao:
        result.encontrado = True
        result.valor = "OBRIGATÓRIA"
        result.confianca = "alta" if len(matches_obrigatoria) >= 2 else "media"
        result.evidencia = matches_obrigatoria[0]['contexto']
    elif matches_facultativa and not matches_obrigatoria:
        result.encontrado = True
        result.valor = "FACULTATIVA"
        result.confianca = "alta" if len(matches_facultativa) >= 2 else "media"
        result.evidencia = matches_facultativa[0]['contexto']
    elif matches_nao and not matches_obrigatoria and not matches_facultativa:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    else:
        # Conflito - prioriza facultativa (mais comum quando há menção)
        if matches_facultativa:
            result.encontrado = True
            result.valor = "FACULTATIVA"
            result.confianca = "baixa"
            result.evidencia = matches_facultativa[0]['contexto']
        elif matches_obrigatoria:
            result.encontrado = True
            result.valor = "OBRIGATÓRIA"
            result.confianca = "baixa"
            result.evidencia = matches_obrigatoria[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NÃO"
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
