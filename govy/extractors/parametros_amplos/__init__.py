"""
Govy - Extractors Regex-Only (32 parâmetros)
============================================

Parâmetros extraídos exclusivamente via regex (custo zero de LLM).

Uso:
    from govy_regex_extractors import extract_all, PARAMETROS_REGEX
    
    resultados = extract_all(texto_do_edital)
    for codigo, resultado in resultados.items():
        print(f"{codigo}: {resultado['valor']} (confiança: {resultado['confianca']})")
"""

from .r_base import RegexResult, fix_encoding

# === EXTRACTORS ORIGINAIS (10) ===
from .r_validade_proposta import extract_r_validade_proposta
from .r_tipo_licitacao import extract_r_tipo_licitacao
from .r_consorcio import extract_r_consorcio
from .r_subcontratacao import extract_r_subcontratacao
from .r_inversao_fases import extract_r_inversao_fases
from .r_vigencia_contrato import extract_r_vigencia_contrato
from .r_amostra import extract_r_amostra
from .r_garantia_execucao import extract_r_garantia_execucao
from .r_prazo_esclarecimento import extract_r_prazo_esclarecimento
from .r_visita_tecnica import extract_r_visita_tecnica

# === EXTRACTORS NOVOS (22) ===
from .r_garantia_proposta import extract_r_garantia_proposta
from .r_preferencia_local import extract_r_preferencia_local
from .r_margem_nacional import extract_r_margem_nacional
from .r_empreitada import extract_r_empreitada
from .r_escritorio_local import extract_r_escritorio_local
from .r_margem_reciclavel import extract_r_margem_reciclavel
from .r_sustentabilidade import extract_r_sustentabilidade
from .r_prova_conceito import extract_r_prova_conceito
from .r_atestado_tecnico import extract_r_atestado_tecnico
from .r_quant_minimo_atestado import extract_r_quant_minimo_atestado
from .r_capital_minimo import extract_r_capital_minimo
from .r_antecipacao_pgto import extract_r_antecipacao_pgto
from .r_reequilibrio import extract_r_reequilibrio
from .r_matriz_riscos import extract_r_matriz_riscos
from .r_prorrogacao import extract_r_prorrogacao
from .r_garantia_objeto import extract_r_garantia_objeto
from .r_obrigacoes_acessorias import extract_r_obrigacoes_acessorias
from .r_prazo_assinatura import extract_r_prazo_assinatura
from .r_certificacao_ambiental import extract_r_certificacao_ambiental
from .r_programa_integridade import extract_r_programa_integridade
from .r_responsabilidade_social import extract_r_responsabilidade_social


# Mapeamento de TODOS os parâmetros regex-only (32 total)
PARAMETROS_REGEX = {
    # === PROCEDIMENTAIS ===
    'r_inversao_fases': {
        'label': 'Inversão das Fases',
        'pergunta': 'O edital estabelece a inversão das fases?',
        'extractor': extract_r_inversao_fases,
    },
    'r_validade_proposta': {
        'label': 'Validade da Proposta',
        'pergunta': 'Qual é o prazo de Validade da Proposta?',
        'extractor': extract_r_validade_proposta,
    },
    'r_prazo_esclarecimento': {
        'label': 'Prazo para Esclarecimentos',
        'pergunta': 'Qual o prazo para pedidos de esclarecimento?',
        'extractor': extract_r_prazo_esclarecimento,
    },
    'r_prazo_assinatura': {
        'label': 'Prazo para Assinatura',
        'pergunta': 'Qual o prazo para assinatura do contrato?',
        'extractor': extract_r_prazo_assinatura,
    },
    'r_visita_tecnica': {
        'label': 'Visita Técnica',
        'pergunta': 'Exige visita técnica obrigatória?',
        'extractor': extract_r_visita_tecnica,
    },
    'r_amostra': {
        'label': 'Exigência de Amostra',
        'pergunta': 'Exige amostra dos produtos?',
        'extractor': extract_r_amostra,
    },
    'r_prova_conceito': {
        'label': 'Prova de Conceito',
        'pergunta': 'Exige prova de conceito (POC)?',
        'extractor': extract_r_prova_conceito,
    },
    'r_tipo_licitacao': {
        'label': 'Tipo de Licitação',
        'pergunta': 'A licitação é por item ou lote?',
        'extractor': extract_r_tipo_licitacao,
    },
    
    # === FINANCEIROS ===
    'r_garantia_proposta': {
        'label': 'Garantia de Proposta',
        'pergunta': 'Exige garantia de proposta?',
        'extractor': extract_r_garantia_proposta,
    },
    'r_garantia_execucao': {
        'label': 'Garantia de Execução',
        'pergunta': 'Exige garantia de execução?',
        'extractor': extract_r_garantia_execucao,
    },
    'r_capital_minimo': {
        'label': 'Capital/Patrimônio Mínimo',
        'pergunta': 'Exige capital ou patrimônio mínimo?',
        'extractor': extract_r_capital_minimo,
    },
    'r_antecipacao_pgto': {
        'label': 'Antecipação de Pagamento',
        'pergunta': 'Permite antecipação de pagamento?',
        'extractor': extract_r_antecipacao_pgto,
    },
    'r_reequilibrio': {
        'label': 'Reequilíbrio Econômico',
        'pergunta': 'Há previsão de reequilíbrio econômico?',
        'extractor': extract_r_reequilibrio,
    },
    'r_vigencia_contrato': {
        'label': 'Vigência do Contrato',
        'pergunta': 'Qual o prazo de vigência do contrato?',
        'extractor': extract_r_vigencia_contrato,
    },
    'r_prorrogacao': {
        'label': 'Prorrogação',
        'pergunta': 'O contrato é prorrogável?',
        'extractor': extract_r_prorrogacao,
    },
    
    # === TÉCNICOS ===
    'r_atestado_tecnico': {
        'label': 'Atestado Técnico',
        'pergunta': 'Exige atestados de capacidade técnica?',
        'extractor': extract_r_atestado_tecnico,
    },
    'r_quant_minimo_atestado': {
        'label': 'Quantitativo Mínimo Atestado',
        'pergunta': 'Exige quantitativo mínimo nos atestados?',
        'extractor': extract_r_quant_minimo_atestado,
    },
    'r_garantia_objeto': {
        'label': 'Garantia do Objeto',
        'pergunta': 'Qual o prazo de garantia do objeto?',
        'extractor': extract_r_garantia_objeto,
    },
    'r_empreitada': {
        'label': 'Modalidade de Empreitada',
        'pergunta': 'Qual a modalidade de empreitada?',
        'extractor': extract_r_empreitada,
    },
    'r_subcontratacao': {
        'label': 'Subcontratação',
        'pergunta': 'Permite subcontratação?',
        'extractor': extract_r_subcontratacao,
    },
    'r_consorcio': {
        'label': 'Consórcio',
        'pergunta': 'Permite consórcio?',
        'extractor': extract_r_consorcio,
    },
    
    # === SUSTENTABILIDADE/SOCIAL ===
    'r_sustentabilidade': {
        'label': 'Sustentabilidade',
        'pergunta': 'Exige critérios de sustentabilidade?',
        'extractor': extract_r_sustentabilidade,
    },
    'r_margem_reciclavel': {
        'label': 'Margem Recicláveis',
        'pergunta': 'Margem para reciclados/biodegradáveis?',
        'extractor': extract_r_margem_reciclavel,
    },
    'r_certificacao_ambiental': {
        'label': 'Certificação Ambiental',
        'pergunta': 'Exige certificações ambientais?',
        'extractor': extract_r_certificacao_ambiental,
    },
    'r_programa_integridade': {
        'label': 'Programa de Integridade',
        'pergunta': 'Exige programa de integridade?',
        'extractor': extract_r_programa_integridade,
    },
    'r_responsabilidade_social': {
        'label': 'Responsabilidade Social',
        'pergunta': 'Exige responsabilidade social?',
        'extractor': extract_r_responsabilidade_social,
    },
    
    # === LOCALIZAÇÃO/PREFERÊNCIA ===
    'r_preferencia_local': {
        'label': 'Preferência Local',
        'pergunta': 'Há preferência por local?',
        'extractor': extract_r_preferencia_local,
    },
    'r_margem_nacional': {
        'label': 'Margem Nacional',
        'pergunta': 'Margem para bens nacionais?',
        'extractor': extract_r_margem_nacional,
    },
    'r_escritorio_local': {
        'label': 'Escritório Local',
        'pergunta': 'Exige escritório na cidade?',
        'extractor': extract_r_escritorio_local,
    },
    
    # === OUTROS ===
    'r_matriz_riscos': {
        'label': 'Matriz de Riscos',
        'pergunta': 'Contém matriz de riscos?',
        'extractor': extract_r_matriz_riscos,
    },
    'r_obrigacoes_acessorias': {
        'label': 'Obrigações Acessórias',
        'pergunta': 'Quais obrigações acessórias?',
        'extractor': extract_r_obrigacoes_acessorias,
    },
}


def extract_all(texto: str) -> dict:
    """Extrai todos os parâmetros de uma vez."""
    texto = fix_encoding(texto)
    resultados = {}
    
    for codigo, config in PARAMETROS_REGEX.items():
        try:
            resultado = config['extractor'](texto)
            resultados[codigo] = {
                'label': config['label'],
                'pergunta': config['pergunta'],
                **resultado.to_dict()
            }
        except Exception as e:
            resultados[codigo] = {
                'label': config['label'],
                'pergunta': config['pergunta'],
                'encontrado': False,
                'valor': '',
                'confianca': 'baixa',
                'evidencia': '',
                'detalhes': {'erro': str(e)}
            }
    
    return resultados


def extract_single(codigo: str, texto: str) -> dict:
    """Extrai um único parâmetro."""
    texto = fix_encoding(texto)
    
    if codigo not in PARAMETROS_REGEX:
        return {'encontrado': False, 'valor': '', 'confianca': 'baixa', 'evidencia': '', 'detalhes': {'erro': f'Desconhecido: {codigo}'}}
    
    config = PARAMETROS_REGEX[codigo]
    try:
        resultado = config['extractor'](texto)
        return {'label': config['label'], 'pergunta': config['pergunta'], **resultado.to_dict()}
    except Exception as e:
        return {'label': config['label'], 'pergunta': config['pergunta'], 'encontrado': False, 'valor': '', 'confianca': 'baixa', 'evidencia': '', 'detalhes': {'erro': str(e)}}


__all__ = ['RegexResult', 'fix_encoding', 'PARAMETROS_REGEX', 'extract_all', 'extract_single']
