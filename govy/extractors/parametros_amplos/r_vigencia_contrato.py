"""
r_vigencia_contrato - Prazo de Vigência do Contrato
===================================================

Extrai o prazo de vigência do contrato/ata.

Padrões comuns:
- "O prazo de vigência da contratação é de 12 (doze) meses"
- "vigência de 12 meses"
- "Ata de Registro de Preços terá validade de 1 (um) ano"
- "prazo de vigência... 6 meses"
"""

import re
from .r_base import RegexResult, extract_context, extract_number, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    # Padrão principal: "prazo de vigência ... X meses/ano"
    r'prazo\s+de\s+vig[êe]ncia[^.]*?(\d+)\s*\([^)]+\)\s*(?:meses|mes|ano|anos)',
    r'prazo\s+de\s+vig[êe]ncia[^.]*?(\d+)\s*(?:meses|mes)',
    r'prazo\s+de\s+vig[êe]ncia[^.]*?(\d+)\s*\([^)]+\)\s*dias',
    r'prazo\s+de\s+vig[êe]ncia[^.]*?(\d+)\s*dias',
    
    # "vigência de X meses"
    r'vig[êe]ncia\s+(?:de\s+)?(?:at[ée]\s+)?(\d+)\s*\([^)]+\)\s*(?:meses|mes)',
    r'vig[êe]ncia\s+(?:de\s+)?(?:at[ée]\s+)?(\d+)\s*(?:meses|mes)',
    
    # "vigência de X ano(s)"
    r'vig[êe]ncia[^.]*?(\d+)\s*\([^)]+\)\s*ano',
    r'vig[êe]ncia[^.]*?(\d+)\s*ano',
    
    # Ata de Registro de Preços
    r'ata[^.]*?(?:vig[êe]ncia|validade)[^.]*?(\d+)\s*\([^)]+\)\s*(?:meses|mes|ano)',
    r'ata[^.]*?(?:vig[êe]ncia|validade)[^.]*?(\d+)\s*(?:meses|mes|ano)',
    
    # Contrato
    r'contrato[^.]*?vig[êe]ncia[^.]*?(\d+)\s*(?:meses|mes|dias)',
    
    # "válida por X dias/meses"
    r'v[áa]lid[oa]\s+por\s+(\d+)\s*\([^)]+\)\s*(?:dias|meses)',
    r'v[áa]lid[oa]\s+por\s+(\d+)\s*(?:dias|meses)',
]

# Contextos negativos específicos
CONTEXTO_NEGATIVO = [
    'validade da proposta',
    'prazo de entrega',
    'prazo de pagamento',
    'garantia',
]


def extract_r_vigencia_contrato(texto: str) -> RegexResult:
    """
    Extrai prazo de vigência do contrato.
    
    Returns:
        RegexResult com valor em meses ou dias (ex: "12 meses", "90 dias")
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
            is_negative = False
            for neg in CONTEXTO_NEGATIVO + TERMOS_NEGATIVOS_COMUNS:
                if neg.lower() in contexto_lower:
                    is_negative = True
                    break
            
            if is_negative:
                continue
            
            try:
                valor = int(match.group(1))
                
                # Determina unidade
                texto_match = match.group(0).lower()
                if 'ano' in texto_match:
                    unidade = 'meses'
                    valor = valor * 12  # Converte anos para meses
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
                        'pattern': pattern
                    })
                elif unidade == 'dias' and 1 <= valor <= 365:
                    matches_encontrados.append({
                        'valor': valor,
                        'unidade': unidade,
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
    return extract_r_vigencia_contrato(texto)
