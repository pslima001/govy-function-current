"""
r_prazo_assinatura - Prazo para Assinatura do Contrato
=====================================================

Extrai o prazo para assinatura do contrato.

Padrões comuns:
- "assinar o contrato no prazo de 5 dias"
- "prazo de 3 dias úteis para assinatura"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    r'assinar\s+(?:o\s+)?(?:termo\s+de\s+)?contrato[^.]*(?:prazo\s+de\s+)?(\d+)\s*\([^)]+\)\s*dias',
    r'assinar\s+(?:o\s+)?(?:termo\s+de\s+)?contrato[^.]*(?:prazo\s+de\s+)?(\d+)\s*dias',
    r'prazo\s+(?:de\s+)?(\d+)\s*\([^)]+\)\s*dias[^.]*(?:para\s+)?assinar',
    r'prazo\s+(?:de\s+)?(\d+)\s*dias[^.]*(?:para\s+)?assinar',
    r'prazo\s+(?:de\s+)?(\d+)\s*dias\s+[úu]teis[^.]*(?:para\s+)?assinatura',
    r'assinatura[^.]*prazo\s+(?:de\s+)?(\d+)\s*dias',
    r'(\d+)\s*\([^)]+\)\s*dias[^.]*assinatura\s+(?:do\s+)?contrato',
    r'(\d+)\s*dias[^.]*assinatura\s+(?:do\s+)?contrato',
    # Patterns para ata de registro de preços
    r'assinar\s+(?:a\s+)?ata[^.]*prazo\s+(?:de\s+)?(\d+)\s*\([^)]+\)\s*dias',
    r'assinar\s+(?:a\s+)?ata[^.]*prazo\s+(?:de\s+)?(\d+)\s*dias',
    r'assinar\s+(?:a\s+)?ata[^.]*(\d+)\s*\([^)]+\)\s*dias',
    r'convocad[oa][^.]*assinar[^.]*(\d+)\s*\([^)]+\)\s*dias',
    r'convocad[oa][^.]*assinar[^.]*(\d+)\s*dias',
    # Novos patterns mais flexíveis
    r'convocad[oa][^.]{0,100}prazo\s+(?:de\s+)?(\d+)\s*\([^)]+\)',
    r'convocad[oa][^.]{0,100}prazo\s+(?:de\s+)?(\d+)\s*dias',
    r'prazo\s+(?:de\s+)?(\d+)\s*\([^)]+\)[^.]*(?:para\s+)?(?:a\s+)?assina',
    r'prazo\s+(?:de\s+)?0?(\d+)\s*dias[^.]*(?:úteis)?[^.]*assina',
    r'(?:no|de)\s+prazo\s+(?:de\s+)?0?(\d+)\s*\([^)]+\)',
]

CONTEXTO_VALIDO = ['assinatura', 'assinar', 'contrato', 'termo', 'ata', 'convocad']


def extract_r_prazo_assinatura(texto: str) -> RegexResult:
    """
    Extrai prazo para assinatura do contrato.
    
    Returns:
        RegexResult com valor em dias
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_encontrados = []
    
    for pattern in PATTERNS:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            
            # Verifica contexto válido
            is_valid = any(cv in contexto_lower for cv in CONTEXTO_VALIDO)
            is_negative = any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS)
            
            if not is_valid or is_negative:
                continue
            
            try:
                dias = int(match.group(1))
                if 1 <= dias <= 30:  # Sanity check
                    matches_encontrados.append({
                        'dias': dias,
                        'contexto': contexto,
                    })
            except (ValueError, IndexError):
                continue
    
    if not matches_encontrados:
        return result
    
    melhor = matches_encontrados[0]
    
    if len(matches_encontrados) >= 2:
        valores = set(m['dias'] for m in matches_encontrados)
        confianca = "alta" if len(valores) == 1 else "media"
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


def extract(texto: str) -> RegexResult:
    return extract_r_prazo_assinatura(texto)
