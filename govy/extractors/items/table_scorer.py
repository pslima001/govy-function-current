"""
table_scorer.py - Scoring de tabelas para identificar candidatas a itens de licitação.

Regras de FORTE CANDIDATO:
1. "Valor Unitário" + "Valor Total" juntos
2. É TABELA + ≥3 indicadores
3. Dentro de "Termo de Referência" + É TABELA + ≥2 indicadores
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .constants import (
    TODOS_INDICADORES,
    INDICADORES_VALORES,
    COMBINACOES_FORTE_CANDIDATO,
    SECOES_TERMO_REFERENCIA,
    MIN_INDICADORES_TABELA,
    MIN_INDICADORES_COM_TR,
    REGEX_VALOR_MONETARIO,
)


@dataclass
class TableScore:
    """Resultado do scoring de uma tabela."""
    table_index: int
    page_number: int
    score: float
    is_forte_candidato: bool
    indicadores_encontrados: List[str]
    tem_valor_unit_total: bool
    dentro_termo_referencia: bool
    tem_valores_monetarios: bool
    row_count: int
    col_count: int
    motivo: str


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação (lowercase, remove acentos básicos)."""
    if not text:
        return ""
    text = text.lower().strip()
    # Normalização básica de acentos
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def extrair_texto_tabela(table: Dict) -> str:
    """Extrai todo o texto de uma tabela normalizada."""
    textos = []
    for cell in table.get("cells", []):
        cell_text = cell.get("text", "")
        if cell_text:
            textos.append(cell_text)
    return " ".join(textos)


def extrair_headers_tabela(table: Dict) -> List[str]:
    """Extrai os headers (primeira linha) de uma tabela."""
    headers = []
    for cell in table.get("cells", []):
        if cell.get("row", -1) == 0:
            cell_text = cell.get("text", "")
            if cell_text:
                headers.append(cell_text)
    return headers


def contar_indicadores(texto: str, indicadores: List[str]) -> Tuple[int, List[str]]:
    """
    Conta quantos indicadores aparecem no texto.
    Retorna (contagem, lista de indicadores encontrados).
    """
    texto_norm = normalize_text(texto)
    encontrados = []
    
    for indicador in indicadores:
        indicador_norm = normalize_text(indicador)
        if indicador_norm in texto_norm:
            encontrados.append(indicador)
    
    return len(encontrados), encontrados


def verificar_combinacao_valor_unit_total(texto: str) -> bool:
    """
    Verifica se o texto contém combinação de Valor Unitário + Valor Total.
    Esta é a Regra 1 de FORTE CANDIDATO.
    """
    texto_norm = normalize_text(texto)
    
    for unit, total in COMBINACOES_FORTE_CANDIDATO:
        unit_norm = normalize_text(unit)
        total_norm = normalize_text(total)
        if unit_norm in texto_norm and total_norm in texto_norm:
            return True
    
    return False


def verificar_dentro_termo_referencia(texto_contexto: str) -> bool:
    """
    Verifica se o contexto indica que estamos dentro de um Termo de Referência.
    """
    texto_norm = normalize_text(texto_contexto)
    
    for secao in SECOES_TERMO_REFERENCIA:
        secao_norm = normalize_text(secao)
        if secao_norm in texto_norm:
            return True
    
    return False


def verificar_valores_monetarios(texto: str) -> bool:
    """Verifica se o texto contém valores monetários (R$)."""
    return bool(REGEX_VALOR_MONETARIO.search(texto))


def score_tabela(
    table: Dict,
    page_number: int,
    texto_contexto: Optional[str] = None
) -> TableScore:
    """
    Calcula o score de uma tabela para determinar se é candidata a conter itens.
    
    Args:
        table: Dicionário com dados da tabela (formato Azure DI normalizado)
        page_number: Número da página onde a tabela está
        texto_contexto: Texto ao redor da tabela para verificar se está em TR
    
    Returns:
        TableScore com todos os detalhes do scoring
    """
    # Extrair texto da tabela
    texto_tabela = extrair_texto_tabela(table)
    headers = extrair_headers_tabela(table)
    texto_headers = " ".join(headers)
    
    # Usar headers prioritariamente, depois texto completo
    texto_para_analise = texto_headers if headers else texto_tabela
    
    # Contar indicadores
    num_indicadores, indicadores_encontrados = contar_indicadores(
        texto_para_analise, 
        TODOS_INDICADORES
    )
    
    # Verificar Regra 1: Valor Unitário + Valor Total juntos
    tem_valor_unit_total = verificar_combinacao_valor_unit_total(texto_para_analise)
    
    # Verificar contexto de Termo de Referência
    contexto_completo = (texto_contexto or "") + " " + texto_tabela
    dentro_tr = verificar_dentro_termo_referencia(contexto_completo)
    
    # Verificar valores monetários
    tem_valores = verificar_valores_monetarios(texto_tabela)
    
    # Metadados da tabela
    row_count = table.get("row_count", 0)
    col_count = table.get("col_count", 0)
    
    # ==========================================================================
    # DETERMINAR SE É FORTE CANDIDATO
    # ==========================================================================
    is_forte = False
    motivo = ""
    score = 0.0
    
    # Regra 1: Valor Unitário + Valor Total juntos
    if tem_valor_unit_total:
        is_forte = True
        motivo = "Regra 1: Valor Unitário + Valor Total juntos"
        score = 1.0
    
    # Regra 2: É TABELA + ≥3 indicadores
    elif num_indicadores >= MIN_INDICADORES_TABELA:
        is_forte = True
        motivo = f"Regra 2: Tabela + {num_indicadores} indicadores (≥{MIN_INDICADORES_TABELA})"
        score = 0.9
    
    # Regra 3: Dentro de TR + É TABELA + ≥2 indicadores
    elif dentro_tr and num_indicadores >= MIN_INDICADORES_COM_TR:
        is_forte = True
        motivo = f"Regra 3: Dentro de TR + {num_indicadores} indicadores (≥{MIN_INDICADORES_COM_TR})"
        score = 0.85
    
    # Candidato fraco (para análise)
    elif num_indicadores >= 1:
        motivo = f"Candidato fraco: apenas {num_indicadores} indicador(es)"
        score = 0.3 * num_indicadores
    
    else:
        motivo = "Não é candidato: nenhum indicador encontrado"
        score = 0.0
    
    # Bônus por valores monetários
    if tem_valores and score > 0:
        score = min(1.0, score + 0.05)
    
    # Bônus por múltiplas linhas (tabelas maiores são mais prováveis)
    if row_count > 5 and score > 0:
        score = min(1.0, score + 0.05)
    
    return TableScore(
        table_index=table.get("table_index", -1),
        page_number=page_number,
        score=score,
        is_forte_candidato=is_forte,
        indicadores_encontrados=indicadores_encontrados,
        tem_valor_unit_total=tem_valor_unit_total,
        dentro_termo_referencia=dentro_tr,
        tem_valores_monetarios=tem_valores,
        row_count=row_count,
        col_count=col_count,
        motivo=motivo,
    )


def filtrar_tabelas_candidatas(
    tables: List[Dict],
    texto_por_pagina: Optional[Dict[int, str]] = None,
    apenas_fortes: bool = True
) -> List[TableScore]:
    """
    Filtra tabelas e retorna apenas as candidatas a conter itens.
    
    Args:
        tables: Lista de tabelas normalizadas (formato Azure DI)
        texto_por_pagina: Dicionário {página: texto} para contexto
        apenas_fortes: Se True, retorna apenas FORTES CANDIDATOS
    
    Returns:
        Lista de TableScore ordenada por score (maior primeiro)
    """
    resultados = []
    
    for table in tables:
        # Determinar página (pode vir de diferentes campos)
        page_num = table.get("page_number", table.get("page", 1))
        
        # Obter contexto da página
        contexto = None
        if texto_por_pagina and page_num in texto_por_pagina:
            contexto = texto_por_pagina[page_num]
        
        score_result = score_tabela(table, page_num, contexto)
        
        if apenas_fortes:
            if score_result.is_forte_candidato:
                resultados.append(score_result)
        else:
            if score_result.score > 0:
                resultados.append(score_result)
    
    # Ordenar por score (maior primeiro)
    resultados.sort(key=lambda x: x.score, reverse=True)
    
    return resultados


# =============================================================================
# FUNÇÕES DE UTILIDADE PARA DEBUG/TESTE
# =============================================================================

def print_score_result(score: TableScore) -> None:
    """Imprime resultado do scoring de forma legível."""
    status = "✅ FORTE" if score.is_forte_candidato else "⚪ Fraco"
    print(f"\n{status} | Tabela #{score.table_index} (Página {score.page_number})")
    print(f"  Score: {score.score:.2f}")
    print(f"  Motivo: {score.motivo}")
    print(f"  Indicadores: {', '.join(score.indicadores_encontrados) or 'Nenhum'}")
    print(f"  Valor Unit+Total: {'Sim' if score.tem_valor_unit_total else 'Não'}")
    print(f"  Dentro de TR: {'Sim' if score.dentro_termo_referencia else 'Não'}")
    print(f"  Valores R$: {'Sim' if score.tem_valores_monetarios else 'Não'}")
    print(f"  Dimensões: {score.row_count} linhas x {score.col_count} colunas")


if __name__ == "__main__":
    # Teste básico
    tabela_teste = {
        "table_index": 0,
        "row_count": 10,
        "col_count": 6,
        "cells": [
            {"row": 0, "col": 0, "text": "Item"},
            {"row": 0, "col": 1, "text": "Descrição"},
            {"row": 0, "col": 2, "text": "Qtde"},
            {"row": 0, "col": 3, "text": "Un."},
            {"row": 0, "col": 4, "text": "Valor Unitário"},
            {"row": 0, "col": 5, "text": "Valor Total"},
            {"row": 1, "col": 0, "text": "1"},
            {"row": 1, "col": 1, "text": "Caneta azul"},
            {"row": 1, "col": 2, "text": "100"},
            {"row": 1, "col": 3, "text": "Un"},
            {"row": 1, "col": 4, "text": "R$ 1,50"},
            {"row": 1, "col": 5, "text": "R$ 150,00"},
        ]
    }
    
    resultado = score_tabela(tabela_teste, page_number=5)
    print_score_result(resultado)
