"""
r_obrigacoes_acessorias - Obrigações Acessórias
==============================================

Identifica obrigações acessórias (relatórios, reuniões, etc).

Padrões comuns:
- "relatórios mensais"
- "reuniões periódicas"
- "apresentar relatório"
"""

import re
from .r_base import RegexResult, extract_context, normalize_text, TERMOS_NEGATIVOS_COMUNS


PATTERNS = [
    r'relat[óo]rios?\s+(?:mensais?|semanais?|peri[óo]dicos?|de\s+acompanhamento)',
    r'apresentar\s+relat[óo]rio',
    r'reuni[õo]es?\s+(?:mensais?|semanais?|peri[óo]dicas?|de\s+acompanhamento)',
    r'participar\s+(?:de\s+)?reuni[õo]es?',
    r'obriga[çc][õo]es\s+acess[óo]rias',
    r'presta[çc][ãa]o\s+de\s+contas?',
    r'fiscaliza[çc][ãa]o\s+(?:mensal|peri[óo]dica)',
    r'treinamento[s]?\s+(?:peri[óo]dico|da\s+equipe)',
    r'suporte\s+t[ée]cnico',
    r'assist[êe]ncia\s+t[ée]cnica',
    r'manuten[çc][ãa]o\s+(?:preventiva|corretiva)',
]


def extract_r_obrigacoes_acessorias(texto: str) -> RegexResult:
    """
    Identifica obrigações acessórias.
    
    Returns:
        RegexResult com valor descritivo
    """
    result = RegexResult()
    texto_norm = normalize_text(texto)
    texto_lower = texto_norm.lower()
    
    obrigacoes_encontradas = []
    evidencias = []
    
    for pattern in PATTERNS:
        for match in re.finditer(pattern, texto_lower, re.IGNORECASE):
            contexto = extract_context(texto_norm, match)
            if not any(neg in contexto.lower() for neg in TERMOS_NEGATIVOS_COMUNS):
                obrigacao = match.group(0).strip()
                if obrigacao not in obrigacoes_encontradas:
                    obrigacoes_encontradas.append(obrigacao)
                    if len(evidencias) < 3:
                        evidencias.append(contexto)
    
    if not obrigacoes_encontradas:
        return result
    
    # Resume as obrigações encontradas
    tipos = []
    if any('relat' in o for o in obrigacoes_encontradas):
        tipos.append('Relatórios')
    if any('reuni' in o for o in obrigacoes_encontradas):
        tipos.append('Reuniões')
    if any('treinamento' in o for o in obrigacoes_encontradas):
        tipos.append('Treinamentos')
    if any('suporte' in o or 'assist' in o for o in obrigacoes_encontradas):
        tipos.append('Suporte')
    if any('manuten' in o for o in obrigacoes_encontradas):
        tipos.append('Manutenção')
    if any('presta' in o for o in obrigacoes_encontradas):
        tipos.append('Prestação de contas')
    
    result.encontrado = True
    result.valor = ', '.join(tipos) if tipos else 'SIM'
    result.confianca = "alta" if len(obrigacoes_encontradas) >= 3 else "media"
    result.evidencia = evidencias[0] if evidencias else ''
    result.detalhes = {
        'obrigacoes': obrigacoes_encontradas[:10],
        'tipos': tipos,
        'total': len(obrigacoes_encontradas)
    }
    
    return result


def extract(texto: str) -> RegexResult:
    return extract_r_obrigacoes_acessorias(texto)
