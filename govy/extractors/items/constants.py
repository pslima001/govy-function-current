"""
Constantes para extração de itens de editais.
Define indicadores, palavras-chave e regras de scoring.
"""

# =============================================================================
# INDICADORES POR GRUPO
# =============================================================================

# Grupo A - Estrutura (identificam colunas de tabela de itens)
INDICADORES_ESTRUTURA = [
    "lote",
    "item",
    "descrição",
    "especificação",
    "descrição do material",
    "especificação dos produtos",
    "descrição da solução",
]

# Grupo B - Quantificação
INDICADORES_QUANTIDADE = [
    "qtde",
    "quantidade",
    "quantitativo",
    "quant",
    "quant.",
    "un.",
    "un",
    "unidade",
    "unidade de fornecimento",
    "uf",
]

# Grupo C - Valores monetários
INDICADORES_VALORES = [
    "valor unitário",
    "valor total",
    "p. unit",
    "p. unit.",
    "p.unit",
    "p.unit.",
    "p. total",
    "p. total.",
    "p.total",
    "p.total.",
    "preço unitário",
    "preço total",
    "valor estimado",
    "vlr. total",
    "vlr total",
    "valor máximo",
    "valor estimado unitário",
]

# Grupo D - Códigos específicos de governo
INDICADORES_CODIGOS = [
    "catmat",
    "catser",
    "código simpas",
    "codigo simpas",
    "código gms",
    "codigo gms",
    "código do item",
    "codigo do item",
    "código",
    "codigo",
]

# Todos os indicadores combinados
TODOS_INDICADORES = (
    INDICADORES_ESTRUTURA +
    INDICADORES_QUANTIDADE +
    INDICADORES_VALORES +
    INDICADORES_CODIGOS
)

# =============================================================================
# SEÇÕES QUE INDICAM TERMO DE REFERÊNCIA
# =============================================================================

SECOES_TERMO_REFERENCIA = [
    "termo de referência",
    "termo de referencia",
    "anexo i",
    "anexo 1",
    "anexo ii",
    "anexo 2",
    "definição do objeto",
    "definicao do objeto",
    "especificações técnicas",
    "especificacoes tecnicas",
    "especificações técnicas e quantidades",
    "do objeto",
    "objeto da contratação",
    "objeto da contratacao",
    "descrição do objeto",
    "descricao do objeto",
]

# =============================================================================
# COMBINAÇÕES DE ALTA CONFIANÇA (REGRA 1)
# =============================================================================

# Se estas palavras aparecerem JUNTAS, é forte candidato
COMBINACOES_FORTE_CANDIDATO = [
    ("valor unitário", "valor total"),
    ("p. unit", "p. total"),
    ("p.unit", "p.total"),
    ("preço unitário", "preço total"),
    ("vlr unitário", "vlr total"),
    ("valor unit", "valor total"),
]

# =============================================================================
# CONFIGURAÇÕES DE SCORING
# =============================================================================

# Mínimo de indicadores para considerar tabela como candidata
MIN_INDICADORES_TABELA = 3

# Mínimo de indicadores se estiver dentro de Termo de Referência
MIN_INDICADORES_COM_TR = 2

# =============================================================================
# PADRÕES REGEX PARA DETECÇÃO
# =============================================================================

import re

# Padrão para detectar valores monetários (R$ X.XXX,XX)
REGEX_VALOR_MONETARIO = re.compile(
    r'R\$\s*[\d.,]+|'
    r'[\d.,]+\s*reais',
    re.IGNORECASE
)

# Padrão para detectar números de item/lote
REGEX_NUMERO_ITEM = re.compile(
    r'\b(?:item|lote)\s*[:\s]*(\d+)\b',
    re.IGNORECASE
)

# Padrão para detectar quantidade com unidade
REGEX_QUANTIDADE = re.compile(
    r'\b(\d+(?:[.,]\d+)?)\s*(?:un|unid|pç|pc|kg|g|l|ml|m|cm|cx|fr|amp|cp|comp)\b',
    re.IGNORECASE
)
