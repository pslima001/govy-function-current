"""
govy_items_extractor - Módulo de extração de itens de editais de licitação.

Este módulo implementa um pipeline de 3 etapas para extrair itens/produtos/serviços
de editais de licitação:

1. PAGE SCANNER (Pré-filtro)
   - Análise leve de texto para identificar páginas candidatas
   - Objetivo: Reduzir custo evitando parse de páginas irrelevantes

2. TABLE SCORER (Scoring)
   - Classifica tabelas por probabilidade de conter itens
   - Regras de FORTE CANDIDATO:
     * Valor Unitário + Valor Total juntos
     * Tabela + ≥3 indicadores
     * Dentro de TR + Tabela + ≥2 indicadores

3. ITEM EXTRACTOR (Extração)
   - Extrai itens das tabelas qualificadas
   - Mapeia colunas automaticamente
   - Captura todos os itens (1 a 400+)

Uso básico:
    from govy_items_extractor import processar_documento
    
    resultado = processar_documento(json_data)
    print(f"Itens extraídos: {resultado.total_itens}")
"""

from .constants import (
    TODOS_INDICADORES,
    INDICADORES_ESTRUTURA,
    INDICADORES_QUANTIDADE,
    INDICADORES_VALORES,
    INDICADORES_CODIGOS,
    SECOES_TERMO_REFERENCIA,
    COMBINACOES_FORTE_CANDIDATO,
    MIN_INDICADORES_TABELA,
    MIN_INDICADORES_COM_TR,
)

from .page_scanner import (
    PageCandidate,
    analisar_pagina,
    scan_documento,
    identificar_paginas_para_parse,
)

from .table_scorer import (
    TableScore,
    score_tabela,
    filtrar_tabelas_candidatas,
)

from .item_extractor import (
    ItemLicitacao,
    ResultadoExtracao,
    extrair_itens_tabela,
    extrair_itens_documento,
    item_to_dict,
)

from .main import (
    processar_documento,
    processar_arquivo,
)

__version__ = "1.0.0"
__all__ = [
    # Constantes
    "TODOS_INDICADORES",
    "INDICADORES_ESTRUTURA",
    "INDICADORES_QUANTIDADE",
    "INDICADORES_VALORES",
    "INDICADORES_CODIGOS",
    "SECOES_TERMO_REFERENCIA",
    "COMBINACOES_FORTE_CANDIDATO",
    "MIN_INDICADORES_TABELA",
    "MIN_INDICADORES_COM_TR",
    # Page Scanner
    "PageCandidate",
    "analisar_pagina",
    "scan_documento",
    "identificar_paginas_para_parse",
    # Table Scorer
    "TableScore",
    "score_tabela",
    "filtrar_tabelas_candidatas",
    # Item Extractor
    "ItemLicitacao",
    "ResultadoExtracao",
    "extrair_itens_tabela",
    "extrair_itens_documento",
    "item_to_dict",
    # Main
    "processar_documento",
    "processar_arquivo",
]
