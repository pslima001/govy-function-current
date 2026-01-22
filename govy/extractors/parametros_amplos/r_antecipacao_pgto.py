"""
r_antecipacao_pgto - Permite Antecipação de Pagamento
====================================================

Identifica se o edital permite antecipação de pagamento.

Padrões comuns:
- "pagamento antecipado"
- "antecipação de pagamento"
- "vedado o pagamento antecipado"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'(?<!n[ãa]o\s)(?<!vedad[oa]\s)pagamento\s+antecipado',
    r'(?<!n[ãa]o\s)(?<!vedad[oa]\s)antecipa[çc][ãa]o\s+(?:de|do)\s+pagamento',
    r'permite\s+(?:o\s+)?pagamento\s+antecipado',
    r'permitid[oa]\s+(?:a\s+)?antecipa[çc][ãa]o',
    r'poder[áa]\s+(?:haver|ser)\s+(?:paga?mento\s+)?antecip',
    r'antecipa[çc][ãa]o\s+(?:de\s+)?(?:at[ée]\s+)?(\d+)\s*[%]',
]

PATTERNS_NAO = [
    r'vedad[oa]\s+(?:o\s+)?pagamento\s+antecipado',
    r'n[ãa]o\s+(?:ser[áa]\s+)?(?:permitid[oa]|admitid[oa])\s+(?:o\s+)?pagamento\s+antecipado',
    r'n[ãa]o\s+(?:haver[áa]|h[áa])\s+(?:pagamento\s+)?antecipa[çc][ãa]o',
    r'vedada\s+(?:a\s+)?antecipa[çc][ãa]o\s+(?:de|do)\s+pagamento',
    r'proibid[oa]\s+(?:o\s+)?pagamento\s+antecipado',
]


def extract_r_antecipacao_pgto(texto: str) -> RegexResult:
    """
    Identifica se permite antecipação de pagamento.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
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
            if not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                if 'não' not in contexto_lower[:30] and 'vedad' not in contexto_lower[:30]:
                    matches_sim.append({'contexto': contexto, 'pattern': pattern})
    
    if not matches_sim and not matches_nao:
        return result
    
    # Prioriza NÃO (vedação é mais comum)
    if matches_nao and not matches_sim:
        result.encontrado = True
        result.valor = "NÃO"
        result.confianca = "alta" if len(matches_nao) >= 2 else "media"
        result.evidencia = matches_nao[0]['contexto']
    elif matches_sim and not matches_nao:
        result.encontrado = True
        result.valor = "SIM"
        result.confianca = "alta" if len(matches_sim) >= 2 else "media"
        result.evidencia = matches_sim[0]['contexto']
    else:
        # Conflito - prioriza NÃO
        if len(matches_nao) >= len(matches_sim):
            result.encontrado = True
            result.valor = "NÃO"
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
    return extract_r_antecipacao_pgto(texto)
