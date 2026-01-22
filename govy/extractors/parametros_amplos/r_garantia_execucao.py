"""
r_garantia_execucao - Exige Garantia de Execução?
=================================================

Identifica se o edital exige garantia de execução contratual.

Padrões comuns:
- "Não haverá exigência da garantia da contratação dos artigos 96 e seguintes"
- "Será exigida a garantia da contratação de que tratam os arts. 96 e seguintes"
- "prestará garantia no valor correspondente a 5% do valor do Contrato"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


# Padrões que indicam NÃO EXIGE
PATTERNS_NAO = [
    r'n[ãa]o\s+haver[áa]\s+exig[êe]ncia\s+(?:da\s+)?garantia\s+(?:da\s+)?contrat',
    r'n[ãa]o\s+haver[áa]\s+exig[êe]ncia\s+(?:da\s+)?garantia\s+(?:da\s+)?contrata[çc][ãa]o',
    r'n[ãa]o\s+haver[áa]\s+exig[êe]ncia\s+de\s+garantia',
    r'n[ãa]o\s+(?:ser[áa]\s+)?exigid[oa]\s+(?:a\s+)?garantia\s+(?:da\s+)?(?:contrata[çc][ãa]o|execu[çc][ãa]o|contrat)',
    r'sem\s+exig[êe]ncia\s+de\s+garantia',
    r'dispensad[oa]\s+(?:a\s+)?(?:exig[êe]ncia\s+de\s+)?garantia',
    r'garantia\s+(?:da\s+)?contrata[çc][ãa]o[^.]*n[ãa]o\s+(?:ser[áa]\s+)?exigid',
    # Novos padrões
    r'n[ãa]o\s+ser[áa]\s+exigid[oa].{0,20}garantia',
    r'garantia[^.]{0,50}n[ãa]o\s+ser[áa]\s+exigid',
    r'garantia.{0,30}facultativ',
]

# Padrões que indicam EXIGE
PATTERNS_SIM = [
    r'ser[áa]\s+exigid[oa]\s+(?:a\s+)?garantia\s+(?:da\s+)?contrata[çc][ãa]o',
    r'exig[êe]ncia\s+(?:da\s+)?garantia\s+(?:da\s+)?(?:contrata[çc][ãa]o|execu[çc][ãa]o)',
    r'prestar[áa]\s+garantia\s+(?:no\s+valor|correspondente|de)',
    r'garantia\s+(?:de\s+execu[çc][ãa]o\s+)?(?:no\s+valor\s+)?(?:de\s+)?(?:\d+[%]|cinco)',
    r'garantia\s+(?:da\s+)?contrata[çc][ãa]o\s+(?:de\s+que\s+tratam|nos\s+termos)',
    r'garantia\s+(?:contratual\s+)?(?:correspondente\s+a\s+)?(?:\d+[%]|\d+\s*por\s*cento)',
    r'exig[êe]ncia\s+de\s+garantia[^.]*(?:art|artigo)[^.]*96',
]

# Padrões para extrair percentual
PATTERN_PERCENTUAL = r'garantia[^.]*?(\d+)\s*(?:%|por\s*cento)'


def extract_r_garantia_execucao(texto: str) -> RegexResult:
    """
    Identifica se o edital exige garantia de execução contratual.
    
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
                matches_nao.append({
                    'contexto': contexto,
                    'pattern': pattern
                })
    
    # Busca padrões de EXIGE
    for pattern in PATTERNS_SIM:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            contexto_lower = contexto.lower()
            if not any(neg in contexto_lower for neg in TERMOS_NEGATIVOS_COMUNS):
                # Verifica se não tem negação no contexto
                if 'não haver' not in contexto_lower and 'nao haver' not in contexto_lower and 'não exig' not in contexto_lower:
                    matches_sim.append({
                        'contexto': contexto,
                        'pattern': pattern
                    })
    
    # Tenta extrair percentual
    match_perc = re.search(PATTERN_PERCENTUAL, texto_lower, re.IGNORECASE)
    if match_perc:
        try:
            perc = int(match_perc.group(1))
            if 1 <= perc <= 30:  # Percentuais típicos de garantia
                percentual = perc
        except (ValueError, IndexError):
            pass
    
    if not matches_sim and not matches_nao:
        return result
    
    # Prioriza NÃO (muito comum em editais)
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
        # Conflito
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
    return extract_r_garantia_execucao(texto)
