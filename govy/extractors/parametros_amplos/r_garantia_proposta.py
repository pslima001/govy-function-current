"""
r_garantia_proposta - Exige Garantia de Proposta?
=================================================

Identifica se o edital exige garantia de proposta (art. 58 da Lei 14.133).

Padrões comuns:
- "Garantia da Proposta, referente à 0,5% do valor estimado"
- "comprovação de recolhimento de garantia de proposta, correspondente ao montante de 1%"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam EXIGE
PATTERNS_SIM = [
    r'garantia\s+(?:da|de)\s+proposta[^.]*(?:\d+[,.]?\d*)\s*(?:%|por\s*cento)',
    r'garantia\s+(?:da|de)\s+proposta[^.]*dever[áa]\s+ser\s+recolhid',
    r'recolhimento\s+(?:de|da)\s+garantia\s+(?:da|de)\s+proposta',
    r'comprovação\s+de\s+recolhimento\s+de\s+garantia\s+de\s+proposta',
    r'art(?:igo)?\.?\s*58[^.]*garantia\s+(?:da|de)\s+proposta',
    r'garantia\s+(?:da|de)\s+proposta[^.]*art(?:igo)?\.?\s*58',
    r'exig[êe]ncia\s+(?:de|da)\s+garantia\s+(?:da|de)\s+proposta',
]

# Padrões que indicam NÃO EXIGE
PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|ser[áa])\s+exig[êe]ncia\s+(?:de|da)\s+garantia\s+(?:da|de)\s+proposta',
    r'dispensad[oa]\s+(?:a\s+)?garantia\s+(?:da|de)\s+proposta',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?garantia\s+(?:da|de)\s+proposta',
]

# Padrão para extrair percentual
PATTERN_PERCENTUAL = r'garantia\s+(?:da|de)\s+proposta[^.]*?(\d+[,.]?\d*)\s*(?:%|por\s*cento)'


def extract_r_garantia_proposta(texto: str) -> RegexResult:
    """
    Identifica se o edital exige garantia de proposta.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO", e percentual se disponível
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    percentual = None
    
    # Busca padrões de NÃO EXIGE
    for pattern in PATTERNS_NAO:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                matches_nao.append({'contexto': contexto, 'pattern': pattern})
    
    # Busca padrões de EXIGE
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            if not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                if 'não' not in contexto_lower and 'dispensad' not in contexto_lower:
                    matches_sim.append({'contexto': contexto, 'pattern': pattern})
    
    # Tenta extrair percentual
    match_perc = re.search(PATTERN_PERCENTUAL, texto_lower, re.IGNORECASE)
    if match_perc:
        try:
            perc = float(match_perc.group(1).replace(',', '.'))
            if 0.1 <= perc <= 5:
                percentual = perc
        except (ValueError, IndexError):
            pass
    
    if not matches_sim and not matches_nao:
        return result
    
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = f"SIM ({percentual}%)" if percentual else "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        if len(matches_nao) > len(matches_sim):
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
        else:
            result.encontrado = True
            result.valor = f"SIM ({percentual}%)" if percentual else "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
    
    result.detalhes = {
        'matches_sim': len(matches_sim),
        'matches_nao': len(matches_nao),
        'percentual': percentual
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_garantia_proposta(texto)
