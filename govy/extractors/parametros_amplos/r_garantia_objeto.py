"""
r_garantia_objeto - Prazo de Garantia do Objeto
==============================================

Identifica o prazo de garantia do objeto contratado.

Padrões comuns:
- "garantia mínima de 12 meses"
- "garantia de 1 ano"
- "prazo de garantia do objeto"
- "garantia do fabricante"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    # Padrão com "pelo menos" 
    r'garantia\s+(?:de\s+)?pelo\s+menos\s+(\d+)\s*\([^)]+\)\s*(?:meses?|anos?|dias?)',
    r'garantia\s+(?:de\s+)?pelo\s+menos\s+(\d+)\s*(?:meses?|anos?|dias?)',
    # Padrão com "no mínimo" e número por extenso em parênteses
    r'garantia[^.]{0,50}(?:no\s+)?m[íi]nimo\s+(\d+)\s*\([^)]+\)\s*(?:meses?|anos?|dias?)',
    r'garantia[^.]{0,50}(?:de\s+)?(\d+)\s*\([^)]+\)\s*(?:meses?|anos?|dias?)',
    # Padrões originais melhorados
    r'garantia\s+(?:m[íi]nima\s+)?(?:de\s+)?(\d+)\s*\([^)]+\)\s*(?:meses|mes|anos?|dias)',
    r'garantia\s+(?:m[íi]nima\s+)?(?:de\s+)?(\d+)\s*(?:meses|mes|anos?|dias)',
    r'prazo\s+de\s+garantia[^.]*?(?:de\s+)?(?:no\s+m[íi]nimo\s+)?(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)',
    r'garantia\s+(?:do\s+)?(?:fabricante|produto|objeto|equipamento|material)[^.]*(\d+)\s*(?:meses|mes|anos?|dias)',
    r'garantia\s+(?:t[ée]cnica\s+)?(?:de\s+)?(\d+)\s*(?:meses|mes|anos?|dias)',
    r'(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)\s+de\s+garantia',
    r'garantia\s+contratual[^.]*?(?:de\s+)?(?:no\s+m[íi]nimo\s+)?(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)',
    r'garantia\s+(?:dos?\s+)?servi[çc]os?[^.]*?(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)',
    # Complementar à garantia legal
    r'complementar\s+[àa]\s+garantia\s+legal[^.]*?(?:de\s+)?(?:no\s+)?m[íi]nimo\s+(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)',
    r'garantia\s+legal[^.]*?(?:ser[áa]\s+de\s+)?(?:no\s+)?m[íi]nimo\s+(\d+)\s*\(?[^)]*\)?\s*(?:meses|mes|anos?|dias)',
    # Padrão "será de X meses" após garantia
    r'garantia[^.]{0,80}ser[áa]\s+de[^.]{0,30}?(\d+)\s*\(?[^)]*\)?\s*(?:meses?|anos?|dias?)',
]

CONTEXTO_VALIDO = ['garantia', 'objeto', 'produto', 'fabricante', 'técnica']

# Contextos a evitar (garantias financeiras, não do objeto)
CONTEXTO_NEGATIVO_ESPECIFICO = [
    'garantia de execução',
    'garantia de proposta',
    'garantia da contratação',
    'caução',
    'fiança',
    'seguro-garantia',
]


def extract_r_garantia_objeto(texto: str) -> RegexResult:
    """
    Extrai prazo de garantia do objeto.
    
    Returns:
        RegexResult com valor em meses/anos/dias
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_encontrados = []
    
    for pattern in PATTERNS:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            
            # Verifica contexto negativo
            is_negative = any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS)
            is_negative_specific = any(neg in contexto_lower for neg in CONTEXTO_NEGATIVO_ESPECIFICO)
            
            if is_negative or is_negative_specific:
                continue
            
            try:
                valor = int(match.group(1))
                texto_match = match.group(0).lower()
                
                if 'ano' in texto_match:
                    unidade = 'meses'
                    valor = valor * 12
                elif 'dia' in texto_match:
                    unidade = 'dias'
                else:
                    unidade = 'meses'
                
                # Sanity check
                if unidade == 'meses' and 1 <= valor <= 120:
                    matches_encontrados.append({
                        'valor': valor,
                        'unidade': unidade,
                        'contexto': contexto,
                    })
                elif unidade == 'dias' and 1 <= valor <= 730:
                    matches_encontrados.append({
                        'valor': valor,
                        'unidade': unidade,
                        'contexto': contexto,
                    })
            except (ValueError, IndexError):
                continue
    
    if not matches_encontrados:
        return result
    
    melhor = matches_encontrados[0]
    
    if len(matches_encontrados) >= 2:
        valores = set((m['valor'], m['unidade']) for m in matches_encontrados)
        confianca = "alta" if len(valores) == 1 else "media"
    else:
        confianca = "media"
    
    result.encontrado = True
    result.valor = f"{melhor['valor']} {melhor['unidade']}"
    result.confianca = confianca
    result.evidencia = melhor['contexto']
    result.detalhes = {
        'valor_numerico': melhor['valor'],
        'unidade': melhor['unidade'],
        'total_matches': len(matches_encontrados)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_garantia_objeto(texto)
