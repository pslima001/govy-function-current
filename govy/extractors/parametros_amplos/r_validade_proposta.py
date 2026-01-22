"""
r_validade_proposta - Prazo de Validade da Proposta
===================================================

Extrai o prazo de validade da proposta em dias.

Padrões comuns:
- "prazo de validade da proposta não será inferior a 60 (sessenta) dias"
- "Validade mínima da proposta: 60 dias"
- "prazo de validade da proposta: 60 (sessenta) dias"
- "Propostas válidas por 60 dias"
"""

import re
from .r_base import RegexResult, extract_context, extract_number, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    # Padrão principal: "prazo de validade da proposta ... X dias"
    r'prazo\s+de\s+validade\s+(?:da|das)?\s*proposta[^.]*?(\d+)\s*\([^)]+\)\s*d[ií]as',
    r'prazo\s+de\s+validade\s+(?:da|das)?\s*proposta[^.]*?(\d+)\s*d[ií]as',
    
    # "validade mínima da proposta: X dias"
    r'validade\s+m[ií]nima\s+(?:da|das)?\s*proposta[:\s]+(\d+)',
    
    # "Propostas válidas por X dias"
    r'proposta[s]?\s+v[áa]lida[s]?\s+por\s+(\d+)',
    
    # "validade da proposta: X dias"  
    r'validade\s+(?:da|das)?\s*proposta[:\s]+(\d+)',
    
    # "validade de, no mínimo, X dias"
    r'validade\s+de[,]?\s*no\s+m[íi]nimo[,]?\s*(\d+)',
    
    # Padrão com extenso: "60 (sessenta) dias"
    r'validade[^.]*?(\d+)\s*\([^)]*\)\s*d[ií]as',
    
    # "não será inferior a X dias"
    r'n[ãa]o\s+ser[áa]\s+inferior\s+a\s+(\d+)\s*\([^)]+\)\s*d[ií]as',
    r'n[ãa]o\s+ser[áa]\s+inferior\s+a\s+(\d+)\s*d[ií]as',
    
    # "deverá ser de no mínimo X dias"
    r'dever[áa]\s+ser\s+de\s+no\s+m[íi]nimo[,]?\s*(\d+)\s*\([^)]+\)\s*d[ií]as',
    r'dever[áa]\s+ser\s+de\s+no\s+m[íi]nimo[,]?\s*(\d+)\s*d[ií]as',
]

# Padrões para contexto negativo (não é sobre validade de proposta)
CONTEXTO_NEGATIVO = [
    'validade da ata',
    'validade do contrato', 
    'validade do registro',
    'prazo de vigência',
]


def extract_r_validade_proposta(texto: str) -> RegexResult:
    """
    Extrai prazo de validade da proposta.
    
    Returns:
        RegexResult com valor em dias (ex: "60 dias")
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_encontrados = []
    
    for pattern in PATTERNS:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            # Extrai contexto
            contexto = extract_context(texto_norm, match)
            
            # Verifica se não é contexto negativo
            is_negative = False
            for neg in CONTEXTO_NEGATIVO + TERMOS_NEGATIVOS_COMUNS:
                if neg.lower() in contexto.lower():
                    is_negative = True
                    break
            
            if is_negative:
                continue
            
            # Extrai o número de dias
            try:
                dias = int(match.group(1))
                if 10 <= dias <= 365:  # Sanity check: entre 10 e 365 dias
                    matches_encontrados.append({
                        'dias': dias,
                        'contexto': contexto,
                        'pattern': pattern
                    })
            except (ValueError, IndexError):
                continue
    
    if not matches_encontrados:
        return result
    
    # Pega o primeiro match válido (geralmente o mais relevante)
    melhor = matches_encontrados[0]
    
    # Determina confiança baseado em quantos matches encontramos
    if len(matches_encontrados) >= 2:
        # Verifica se todos concordam no valor
        valores = set(m['dias'] for m in matches_encontrados)
        if len(valores) == 1:
            confianca = "alta"
        else:
            confianca = "media"
    else:
        confianca = "media"
    
    result.encontrado = True
    result.valor = f"{melhor['dias']} dias"
    result.confianca = confianca
    result.evidencia = melhor['contexto']
    result.detalhes = {
        'dias': melhor['dias'],
        'total_matches': len(matches_encontrados)
    }
    
    return result


# Alias para manter consistência com outros extractors
def extract(texto: str) -> RegexResult:
    return extract_r_validade_proposta(texto)
