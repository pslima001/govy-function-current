"""
r_prazo_esclarecimento - Prazo para Pedidos de Esclarecimento
=============================================================

Extrai o prazo para pedidos de esclarecimento/impugnação.

Padrões comuns:
- "até 3 (três) dias úteis antes da data da abertura do certame"
- "até 03 (três) dias úteis antes da data fixada para abertura"
- "esclarecimentos até 2 dias úteis antes"
"""

import re
from .r_base import RegexResult, extract_context, extract_number, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    # "até X dias úteis antes"
    r'at[ée]\s+(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis\s*(?:antes|anterior)',
    r'at[ée]\s+(\d+)\s*dias\s*[úu]teis\s*(?:antes|anterior)',
    
    # "no prazo de até X dias úteis"
    r'(?:no\s+)?prazo\s+de\s+at[ée]\s+(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis',
    r'(?:no\s+)?prazo\s+de\s+at[ée]\s+(\d+)\s*dias\s*[úu]teis',
    
    # "protocolar o pedido até X dias"
    r'protocolar\s+(?:o\s+)?pedido\s+at[ée]\s+(\d+)\s*\([^)]+\)\s*dias',
    r'protocolar\s+(?:o\s+)?pedido\s+at[ée]\s+(\d+)\s*dias',
    
    # "esclarecimentos até X dias"
    r'esclarecimento[s]?\s+at[ée]\s+(\d+)\s*dias',
    
    # "X dias úteis anteriores"
    r'(\d+)\s*dias\s*[úu]teis\s*anterior',
    r'(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis\s*anterior',
    
    # Formato genérico com dias úteis e contexto
    r'(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis[^.]{0,50}(?:abertura|certame|sess[ãa]o)',
    r'(\d+)\s*dias\s*[úu]teis[^.]{0,50}(?:abertura|certame|sess[ãa]o)',
    
    # "impugnação... no prazo de X dias"
    r'impugna[çc][ãa]o[^.]*?(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis',
    r'impugna[çc][ãa]o[^.]*?(\d+)\s*dias\s*[úu]teis',
    
    # "responder ... no prazo de até X dias úteis"
    r'responder[^.]*?(?:no\s+)?prazo\s+de\s+at[ée]\s+(\d+)\s*\([^)]+\)\s*dias\s*[úu]teis',
    r'responder[^.]*?(?:no\s+)?prazo\s+de\s+at[ée]\s+(\d+)\s*dias\s*[úu]teis',
    
    # Novos padrões mais flexíveis
    r'(\d+)\s*\([^)]+\)\s*dias[^.]{0,30}esclarecimento',
    r'(\d+)\s*dias[^.]{0,30}esclarecimento',
    r'pedido[s]?\s+de\s+(?:esclarecimento|informa)[^.]*?(\d+)\s*dias',
]

# Contextos que indicam esclarecimento/impugnação
CONTEXTOS_VALIDOS = [
    'esclarecimento', 'impugna', 'pedido', 'protocolar',
    'abertura', 'certame', 'sessão', 'sessao', 'proposta'
]


def extract_r_prazo_esclarecimento(texto: str) -> RegexResult:
    """
    Extrai prazo para pedidos de esclarecimento.
    
    Returns:
        RegexResult com valor em dias úteis (ex: "3 dias úteis")
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_encontrados = []
    
    for pattern in PATTERNS:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            
            # Verifica se é contexto válido (esclarecimento/impugnação)
            is_valid = any(ctx in contexto_lower for ctx in CONTEXTOS_VALIDOS)
            is_negative = any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS)
            
            if not is_valid or is_negative:
                continue
            
            try:
                dias = int(match.group(1))
                if 1 <= dias <= 10:  # Sanity check: entre 1 e 10 dias úteis
                    matches_encontrados.append({
                        'dias': dias,
                        'contexto': contexto,
                        'pattern': pattern
                    })
            except (ValueError, IndexError):
                continue
    
    if not matches_encontrados:
        return result
    
    # Pega o primeiro match válido
    melhor = matches_encontrados[0]
    
    # Determina confiança
    if len(matches_encontrados) >= 2:
        valores = set(m['dias'] for m in matches_encontrados)
        confianca = "alta" if len(valores) == 1 else "media"
    else:
        confianca = "media"
    
    result.encontrado = True
    result.valor = f"{melhor['dias']} dias úteis"
    result.confianca = confianca
    result.evidencia = melhor['contexto']
    result.detalhes = {
        'dias': melhor['dias'],
        'total_matches': len(matches_encontrados)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_prazo_esclarecimento(texto)
