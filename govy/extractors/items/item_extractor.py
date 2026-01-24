"""
item_extractor.py - Extração de itens de licitação das tabelas qualificadas.

Este módulo extrai os produtos/serviços (itens) das tabelas que foram
identificadas como FORTES CANDIDATOS pelo table_scorer.

Objetivo: Capturar TODOS os itens, seja 1 ou 400.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from .constants import REGEX_VALOR_MONETARIO


@dataclass
class ItemLicitacao:
    """Representa um item de licitação extraído."""
    numero: Optional[str] = None  # Número do item/lote
    descricao: str = ""           # Descrição do produto/serviço
    quantidade: Optional[str] = None
    unidade: Optional[str] = None
    valor_unitario: Optional[str] = None
    valor_total: Optional[str] = None
    codigo_catmat: Optional[str] = None
    codigo_catser: Optional[str] = None
    lote: Optional[str] = None
    outros: Dict[str, str] = field(default_factory=dict)  # Campos adicionais
    
    # Metadados
    page_number: int = 0
    table_index: int = 0
    row_index: int = 0
    confianca: float = 0.0


@dataclass
class ResultadoExtracao:
    """Resultado completo da extração de itens."""
    itens: List[ItemLicitacao]
    total_itens: int
    paginas_processadas: List[int]
    tabelas_processadas: int
    erros: List[str]


# =============================================================================
# MAPEAMENTO DE COLUNAS
# =============================================================================

# Padrões para identificar tipo de coluna
COLUMN_PATTERNS = {
    "numero": [
        r"^item$", r"^n[úu]mero$", r"^n\.?º?$", r"^#$", r"^seq$",
        r"^lote$", r"^cod\.?$", r"^c[óo]d$"
    ],
    "lote": [
        r"^lote$", r"^lote\s*n?\.?º?$", r"^grupo$"
    ],
    "descricao": [
        r"descri[çc][ãa]o", r"especifica[çc][ãa]o", r"^produto$", r"^material$",
        r"^servi[çc]o$", r"^objeto$", r"descri[çc][ãa]o\s+do\s+material",
        r"descri[çc][ãa]o\s+detalhada", r"^medicamento$", r"^apresenta[çc][ãa]o$",
        r"^nome$", r"^denomina[çc][ãa]o$"
    ],
    "quantidade": [
        r"^qtd[ae]?\.?$", r"^quantidade$", r"^quant\.?$", r"^qde$", r"^qt$"
    ],
    "unidade": [
        r"^un\.?$", r"^unid\.?$", r"^unidade$", r"^uf$",
        r"unidade\s+de\s+fornecimento", r"^medida$"
    ],
    "valor_unitario": [
        r"valor\s+unit[áa]rio", r"pre[çc]o\s+unit[áa]rio",
        r"^p\.?\s*unit\.?$", r"^v\.?\s*unit\.?$", r"^vl\.?\s*unit\.?$",
        r"valor\s+unit", r"unit[áa]rio"
    ],
    "valor_total": [
        r"valor\s+total", r"pre[çc]o\s+total",
        r"^p\.?\s*total\.?$", r"^v\.?\s*total\.?$", r"^vl\.?\s*total\.?$",
        r"vlr\.?\s*total"
    ],
    "codigo_catmat": [
        r"^catmat$", r"c[óo]digo\s+catmat", r"cod\.?\s*catmat"
    ],
    "codigo_catser": [
        r"^catser$", r"c[óo]digo\s+catser", r"cod\.?\s*catser"
    ],
}

# Colunas que podem conter descrição se não houver coluna específica
COLUNAS_DESCRICAO_FALLBACK = [
    r"especifica[çc]", r"produto", r"material", r"servi[çc]o",
    r"medicamento", r"nome", r"denomina"
]


def normalizar_header(header: str) -> str:
    """Normaliza header para comparação."""
    if not header:
        return ""
    header = header.lower().strip()
    header = re.sub(r'\s+', ' ', header)
    return header


def identificar_tipo_coluna(header: str) -> Optional[str]:
    """Identifica o tipo de uma coluna pelo seu header."""
    header_norm = normalizar_header(header)
    
    for tipo, patterns in COLUMN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, header_norm, re.IGNORECASE):
                return tipo
    
    return None


def mapear_colunas(headers: List[str]) -> Dict[int, str]:
    """
    Mapeia índices de colunas para seus tipos.
    
    Returns:
        Dict {índice_coluna: tipo_coluna}
    """
    mapeamento = {}
    
    for idx, header in enumerate(headers):
        tipo = identificar_tipo_coluna(header)
        if tipo:
            mapeamento[idx] = tipo
    
    # Se não encontrou coluna de descrição, tentar fallback
    if "descricao" not in mapeamento.values():
        header_norm_list = [(i, normalizar_header(h)) for i, h in enumerate(headers)]
        
        # Tentar encontrar coluna com texto mais longo (provavelmente descrição)
        for i, header_norm in header_norm_list:
            if i in mapeamento:
                continue
            for pattern in COLUNAS_DESCRICAO_FALLBACK:
                if re.search(pattern, header_norm, re.IGNORECASE):
                    mapeamento[i] = "descricao"
                    break
            if "descricao" in mapeamento.values():
                break
    
    return mapeamento


def encontrar_coluna_descricao_por_conteudo(
    linhas: Dict[int, Dict[int, str]], 
    header_row: int,
    headers: List[str]
) -> Optional[int]:
    """
    Tenta encontrar coluna de descrição pelo conteúdo (texto mais longo).
    """
    if not linhas:
        return None
    
    # Pegar uma linha de dados
    data_rows = [r for r in linhas.keys() if r > header_row]
    if not data_rows:
        return None
    
    sample_row = linhas[data_rows[0]]
    
    # Encontrar coluna com texto mais longo
    max_len = 0
    best_col = None
    
    for col_idx, valor in sample_row.items():
        if len(valor) > max_len:
            # Verificar se não é número puro
            if not re.match(r'^[\d.,\s]+$', valor.strip()):
                max_len = len(valor)
                best_col = col_idx
    
    return best_col


def verificar_coluna_unidade_e_descricao(
    linhas: Dict[int, Dict[int, str]],
    header_row: int,
    mapeamento: Dict[int, str]
) -> Dict[int, str]:
    """
    Verifica se colunas mapeadas como 'unidade' são na verdade descrições.
    
    Heurística: se o conteúdo de uma coluna 'unidade' tem mais de 15 caracteres
    e não é uma abreviação comum (UN, UND, KG, etc.), provavelmente é descrição.
    """
    UNIDADES_VALIDAS = {
        'un', 'und', 'unid', 'unidade', 'kg', 'g', 'l', 'ml', 'm', 'cm', 'mm',
        'pc', 'pç', 'cx', 'caixa', 'fr', 'frasco', 'amp', 'ampola', 'cp', 
        'comprimido', 'comp', 'tb', 'tubo', 'pt', 'pacote', 'rolo', 'metro',
        'litro', 'grama', 'quilo', 'dose', 'par', 'jogo', 'kit', 'serv',
        'servico', 'diaria', 'hora', 'mes', 'ano', 'fixo', 'sv', 'svc'
    }
    
    novo_mapeamento = mapeamento.copy()
    
    # Pegar linhas de dados
    data_rows = [r for r in linhas.keys() if r > header_row]
    if not data_rows:
        return novo_mapeamento
    
    # Verificar colunas mapeadas como unidade
    colunas_unidade = [col for col, tipo in mapeamento.items() if tipo == "unidade"]
    
    for col_idx in colunas_unidade:
        # Verificar conteúdo em algumas linhas
        conteudos_longos = 0
        total_amostras = 0
        
        for row_idx in data_rows[:5]:  # Verificar até 5 linhas
            if row_idx in linhas and col_idx in linhas[row_idx]:
                valor = linhas[row_idx][col_idx].strip().lower()
                total_amostras += 1
                
                # Verificar se é uma unidade válida
                if valor not in UNIDADES_VALIDAS and len(valor) > 10:
                    conteudos_longos += 1
        
        # Se maioria dos conteúdos são longos, reclassificar como descrição
        if total_amostras > 0 and conteudos_longos / total_amostras >= 0.5:
            # Verificar se já não temos descrição
            if "descricao" not in novo_mapeamento.values():
                novo_mapeamento[col_idx] = "descricao"
    
    return novo_mapeamento


# =============================================================================
# EXTRAÇÃO DE ITENS
# =============================================================================

def extrair_headers_tabela(table: Dict) -> Tuple[List[str], int]:
    """
    Extrai headers de uma tabela e retorna a linha onde estão.
    
    Returns:
        (lista_headers, linha_header)
    """
    cells = table.get("cells", [])
    
    # Agrupar células por linha
    linhas = {}
    for cell in cells:
        row = cell.get("row", 0)
        if row not in linhas:
            linhas[row] = []
        linhas[row].append(cell)
    
    # A primeira linha geralmente é o header
    # Mas às vezes pode haver título na linha 0
    for row_idx in sorted(linhas.keys()):
        row_cells = linhas[row_idx]
        
        # Verificar se parece header (múltiplas células com texto)
        textos = [c.get("text", "") for c in row_cells]
        textos_preenchidos = [t for t in textos if t.strip()]
        
        if len(textos_preenchidos) >= 2:
            # Verificar se algum texto é identificável como tipo de coluna
            tipos_encontrados = sum(1 for t in textos if identificar_tipo_coluna(t))
            if tipos_encontrados >= 1:
                # Ordenar células por coluna
                row_cells.sort(key=lambda c: c.get("col", 0))
                headers = [c.get("text", "") for c in row_cells]
                return headers, row_idx
    
    return [], 0


def extrair_itens_tabela(
    table: Dict,
    page_number: int = 0
) -> List[ItemLicitacao]:
    """
    Extrai itens de uma tabela qualificada.
    
    Args:
        table: Dicionário da tabela (formato Azure DI normalizado)
        page_number: Número da página
    
    Returns:
        Lista de ItemLicitacao extraídos
    """
    cells = table.get("cells", [])
    table_index = table.get("table_index", 0)
    
    if not cells:
        return []
    
    # Extrair headers e mapear colunas
    headers, header_row = extrair_headers_tabela(table)
    if not headers:
        return []
    
    mapeamento = mapear_colunas(headers)
    
    # Agrupar células por linha
    linhas = {}
    for cell in cells:
        row = cell.get("row", 0)
        col = cell.get("col", 0)
        if row not in linhas:
            linhas[row] = {}
        linhas[row][col] = cell.get("text", "")
    
    # Se não encontrou descrição, tentar por conteúdo
    if "descricao" not in mapeamento.values():
        col_desc = encontrar_coluna_descricao_por_conteudo(linhas, header_row, headers)
        if col_desc is not None and col_desc not in mapeamento:
            mapeamento[col_desc] = "descricao"
    
    # Verificar se colunas de 'unidade' são na verdade descrições
    mapeamento = verificar_coluna_unidade_e_descricao(linhas, header_row, mapeamento)
    
    if not mapeamento:
        # Não conseguiu mapear nenhuma coluna
        return []
    
    # Extrair itens (pular linha de header)
    itens = []
    
    for row_idx in sorted(linhas.keys()):
        if row_idx <= header_row:
            continue  # Pular header
        
        row_data = linhas[row_idx]
        
        # Criar item
        item = ItemLicitacao(
            page_number=page_number,
            table_index=table_index,
            row_index=row_idx,
        )
        
        # Preencher campos mapeados
        campos_preenchidos = 0
        
        for col_idx, tipo in mapeamento.items():
            valor = row_data.get(col_idx, "").strip()
            if not valor:
                continue
            
            campos_preenchidos += 1
            
            if tipo == "numero":
                item.numero = valor
            elif tipo == "lote":
                item.lote = valor
            elif tipo == "descricao":
                item.descricao = valor
            elif tipo == "quantidade":
                item.quantidade = valor
            elif tipo == "unidade":
                item.unidade = valor
            elif tipo == "valor_unitario":
                item.valor_unitario = valor
            elif tipo == "valor_total":
                item.valor_total = valor
            elif tipo == "codigo_catmat":
                item.codigo_catmat = valor
            elif tipo == "codigo_catser":
                item.codigo_catser = valor
        
        # Coletar campos não mapeados
        for col_idx, valor in row_data.items():
            if col_idx not in mapeamento and valor.strip():
                header_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                item.outros[header_name] = valor.strip()
        
        # Validar item (precisa ter pelo menos descrição ou número)
        if item.descricao or item.numero:
            # Calcular confiança baseada em campos preenchidos
            item.confianca = min(1.0, campos_preenchidos / 5)
            itens.append(item)
    
    return itens


def extrair_itens_documento(
    tables: List[Dict],
    scores: List[Any] = None,  # TableScore do table_scorer
    texto_por_pagina: Optional[Dict[int, str]] = None
) -> ResultadoExtracao:
    """
    Extrai todos os itens de um documento processado.
    
    Args:
        tables: Lista de tabelas normalizadas
        scores: Lista de TableScore (se disponível, processa apenas fortes)
        texto_por_pagina: Texto por página para contexto
    
    Returns:
        ResultadoExtracao com todos os itens encontrados
    """
    todos_itens = []
    paginas_processadas = set()
    tabelas_processadas = 0
    erros = []
    
    # Se temos scores, processar apenas tabelas fortes
    if scores:
        tabelas_fortes_idx = {s.table_index for s in scores if s.is_forte_candidato}
    else:
        tabelas_fortes_idx = None
    
    for table in tables:
        table_idx = table.get("table_index", 0)
        page_num = table.get("page_number", table.get("page", 1))
        
        # Filtrar por score se disponível
        if tabelas_fortes_idx is not None:
            if table_idx not in tabelas_fortes_idx:
                continue
        
        try:
            itens = extrair_itens_tabela(table, page_number=page_num)
            todos_itens.extend(itens)
            paginas_processadas.add(page_num)
            tabelas_processadas += 1
            
        except Exception as e:
            erros.append(f"Erro na tabela {table_idx} (página {page_num}): {str(e)}")
    
    return ResultadoExtracao(
        itens=todos_itens,
        total_itens=len(todos_itens),
        paginas_processadas=sorted(list(paginas_processadas)),
        tabelas_processadas=tabelas_processadas,
        erros=erros,
    )


# =============================================================================
# UTILIDADES
# =============================================================================

def item_to_dict(item: ItemLicitacao) -> Dict:
    """Converte ItemLicitacao para dicionário."""
    return {
        "numero": item.numero,
        "lote": item.lote,
        "descricao": item.descricao,
        "quantidade": item.quantidade,
        "unidade": item.unidade,
        "valor_unitario": item.valor_unitario,
        "valor_total": item.valor_total,
        "codigo_catmat": item.codigo_catmat,
        "codigo_catser": item.codigo_catser,
        "outros": item.outros,
        "_meta": {
            "page_number": item.page_number,
            "table_index": item.table_index,
            "row_index": item.row_index,
            "confianca": item.confianca,
        }
    }


def print_item(item: ItemLicitacao) -> None:
    """Imprime item de forma legível."""
    print(f"\n📦 Item {item.numero or '?'} (Pág. {item.page_number})")
    print(f"   Descrição: {item.descricao[:80]}..." if len(item.descricao) > 80 else f"   Descrição: {item.descricao}")
    if item.quantidade:
        print(f"   Quantidade: {item.quantidade} {item.unidade or ''}")
    if item.valor_unitario:
        print(f"   Valor Unit.: {item.valor_unitario}")
    if item.valor_total:
        print(f"   Valor Total: {item.valor_total}")
    if item.codigo_catmat:
        print(f"   CATMAT: {item.codigo_catmat}")
    print(f"   Confiança: {item.confianca:.0%}")


def print_resultado_extracao(resultado: ResultadoExtracao) -> None:
    """Imprime resumo da extração."""
    print("\n" + "="*60)
    print("📊 RESULTADO DA EXTRAÇÃO DE ITENS")
    print("="*60)
    print(f"Total de itens: {resultado.total_itens}")
    print(f"Tabelas processadas: {resultado.tabelas_processadas}")
    print(f"Páginas: {resultado.paginas_processadas}")
    
    if resultado.erros:
        print(f"\n⚠️ Erros ({len(resultado.erros)}):")
        for erro in resultado.erros:
            print(f"  - {erro}")
    
    print("\n--- ITENS EXTRAÍDOS ---")
    for item in resultado.itens[:10]:  # Mostrar primeiros 10
        print_item(item)
    
    if resultado.total_itens > 10:
        print(f"\n... e mais {resultado.total_itens - 10} itens")




if __name__ == "__main__":
    # Teste com tabela exemplo
    tabela_teste = {
        "table_index": 0,
        "row_count": 5,
        "col_count": 6,
        "cells": [
            # Header
            {"row": 0, "col": 0, "text": "Item"},
            {"row": 0, "col": 1, "text": "Descrição do Material"},
            {"row": 0, "col": 2, "text": "Qtde"},
            {"row": 0, "col": 3, "text": "Un."},
            {"row": 0, "col": 4, "text": "Valor Unitário"},
            {"row": 0, "col": 5, "text": "Valor Total"},
            # Item 1
            {"row": 1, "col": 0, "text": "1"},
            {"row": 1, "col": 1, "text": "PARACETAMOL 500MG COMPRIMIDO"},
            {"row": 1, "col": 2, "text": "10000"},
            {"row": 1, "col": 3, "text": "CP"},
            {"row": 1, "col": 4, "text": "R$ 0,15"},
            {"row": 1, "col": 5, "text": "R$ 1.500,00"},
            # Item 2
            {"row": 2, "col": 0, "text": "2"},
            {"row": 2, "col": 1, "text": "DIPIRONA 500MG COMPRIMIDO"},
            {"row": 2, "col": 2, "text": "5000"},
            {"row": 2, "col": 3, "text": "CP"},
            {"row": 2, "col": 4, "text": "R$ 0,20"},
            {"row": 2, "col": 5, "text": "R$ 1.000,00"},
            # Item 3
            {"row": 3, "col": 0, "text": "3"},
            {"row": 3, "col": 1, "text": "AMOXICILINA 500MG CÁPSULA"},
            {"row": 3, "col": 2, "text": "2000"},
            {"row": 3, "col": 3, "text": "CP"},
            {"row": 3, "col": 4, "text": "R$ 0,50"},
            {"row": 3, "col": 5, "text": "R$ 1.000,00"},
        ]
    }
    
    itens = extrair_itens_tabela(tabela_teste, page_number=5)
    
    resultado = ResultadoExtracao(
        itens=itens,
        total_itens=len(itens),
        paginas_processadas=[5],
        tabelas_processadas=1,
        erros=[]
    )
    
    print_resultado_extracao(resultado)
