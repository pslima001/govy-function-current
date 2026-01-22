"""
r_margem_nacional - Margem de Preferência para Bens Nacionais
=============================================================

Identifica se o edital prevê margem de preferência para bens nacionais.

Padrões comuns:
- "margem de preferência para produtos manufaturados e para serviços nacionais"
- "margem de preferência... Decreto nº 7.174"
- "preferência para bens e serviços produzidos no país"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam SIM
PATTERNS_SIM = [
    r'margem\s+de\s+prefer[êe]ncia[^.]*(?:nacion|brasil|pa[íi]s)',
    r'margem\s+de\s+prefer[êe]ncia[^.]*(?:produto|bem|servi[çc]o)',
    r'prefer[êe]ncia[^.]*(?:bens?|produtos?|servi[çc]os?)[^.]*(?:nacion|brasil|pa[íi]s)',
    r'decreto\s+(?:n[º°]?\s*)?7\.?174',
    r'prefer[êe]ncia[^.]*manufaturad',
    r'margem\s+de\s+prefer[êe]ncia[^.]*(?:\d+)\s*[%]',
]

# Padrões que indicam NÃO
PATTERNS_NAO = [
    r'n[ãa]o\s+(?:haver[áa]|ser[áa]|h[áa])\s+(?:aplica[çc][ãa]o\s+de\s+)?margem\s+de\s+prefer[êe]ncia',
    r'sem\s+margem\s+de\s+prefer[êe]ncia',
    r'n[ãa]o\s+se\s+aplica[^.]*margem\s+de\s+prefer[êe]ncia',
]

PATTERN_PERCENTUAL = r'margem\s+de\s+prefer[êe]ncia[^.]*?(\d+)\s*[%]'


def extract_r_margem_nacional(texto: str) -> RegexResult:
    """
    Identifica se há margem de preferência para bens nacionais.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO"
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    matches_sim = []
    matches_nao = []
    percentual = None
    
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
                if 'não' not in contexto_lower[:30]:
                    matches_sim.append({'contexto': contexto, 'pattern': pattern})
    
    # Extrair percentual
    match_perc = re.search(PATTERN_PERCENTUAL, texto_lower)
    if match_perc:
        try:
            percentual = int(match_perc.group(1))
        except:
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
        if len(matches_sim) >= len(matches_nao):
            result.encontrado = True
            result.valor = f"SIM ({percentual}%)" if percentual else "SIM"
            result.confianca = "baixa"
            result.evidencia = matches_sim[0]['contexto']
        else:
            result.encontrado = True
            result.valor = "NÃO"
            result.confianca = "baixa"
            result.evidencia = matches_nao[0]['contexto']
    
    result.detalhes = {'matches_sim': len(matches_sim), 'matches_nao': len(matches_nao), 'percentual': percentual}
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_margem_nacional(texto)
