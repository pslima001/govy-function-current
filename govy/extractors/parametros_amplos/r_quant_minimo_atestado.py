"""
r_quant_minimo_atestado - Quantitativo Mínimo nos Atestados
==========================================================

Identifica se o edital exige quantitativo mínimo nos atestados.

Padrões comuns:
- "atestados que comprovem, no mínimo, 50%"
- "atestados... quantidade mínima de 35%"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS_SIM = [
    r'atestado[s]?[^.]*(?:no\s+m[íi]nimo|m[íi]nim[oa])[^.]*(\d+)\s*[%]',
    r'atestado[s]?[^.]*quantidade\s+m[íi]nima[^.]*(\d+)\s*[%]',
    r'comprova[çc][ãa]o[^.]*(?:no\s+m[íi]nimo|m[íi]nim[oa])[^.]*(\d+)\s*[%]',
    r'(?:no\s+m[íi]nimo|m[íi]nim[oa])[^.]*(\d+)\s*[%][^.]*atestado',
    r'atestado[s]?[^.]*(?:equivalente|correspondente)[^.]*(\d+)\s*[%]',
    r'quantitativo[s]?\s+m[íi]nimo[s]?[^.]*atestado',
    r'parcela\s+de\s+maior\s+relev[âa]ncia',
]

PATTERNS_NAO = [
    r'n[ãa]o\s+(?:ser[áa]|haver[áa])\s+(?:exigid[oa]|necess[áa]ri[oa])[^.]*quantitativo\s+m[íi]nimo',
    r'sem\s+(?:exig[êe]ncia\s+de\s+)?quantitativo\s+m[íi]nimo',
    r'independente\s+(?:de|do)\s+quantitativo',
]

PATTERN_PERCENTUAL = r'(?:no\s+m[íi]nimo|m[íi]nim[oa]|quantidade\s+m[íi]nima)[^.]*?(\d+)\s*[%]'


def extract_r_quant_minimo_atestado(texto: str) -> RegexResult:
    """
    Identifica se exige quantitativo mínimo nos atestados.
    
    Returns:
        RegexResult com valor "SIM" ou "NÃO", e percentual se disponível
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
                    # Tenta extrair percentual
                    if match.lastindex and match.lastindex >= 1:
                        try:
                            percentual = int(match.group(1))
                        except:
                            pass
    
    # Busca adicional por percentual
    if not percentual:
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
    return extract_r_quant_minimo_atestado(texto)
