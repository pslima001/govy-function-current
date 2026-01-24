"""
main.py - Módulo principal de extração de itens de editais.

Integra:
- page_scanner: Identificação de páginas candidatas (pré-filtro)
- table_scorer: Scoring de tabelas
- item_extractor: Extração dos itens

Uso:
    python main.py arquivo_parseado.json
"""

import json
import sys
from typing import Dict, List, Optional
from pathlib import Path

from .constants import *
from .page_scanner import scan_documento, identificar_paginas_para_parse, print_resultado_scan
from .table_scorer import filtrar_tabelas_candidatas, print_score_result, TableScore
from .item_extractor import (
    extrair_itens_documento, 
    item_to_dict, 
    print_resultado_extracao,
    ResultadoExtracao
)


def carregar_json_parseado(filepath: str) -> Dict:
    """Carrega arquivo JSON parseado pelo Azure DI."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extrair_texto_por_pagina(texto_completo: str, page_count: int) -> Dict[int, str]:
    """
    Tenta dividir texto completo por páginas (heurística).
    Em produção, isso viria do Azure DI com metadados de página.
    """
    # Heurística: dividir por marcadores de página ou por tamanho
    # Por enquanto, retorna tudo como página 1
    return {1: texto_completo}


def processar_documento(
    json_data: Dict,
    verbose: bool = True
) -> ResultadoExtracao:
    """
    Processa documento JSON parseado e extrai itens.
    
    Args:
        json_data: Dados do JSON parseado (Azure DI)
        verbose: Se True, imprime detalhes do processamento
    
    Returns:
        ResultadoExtracao com todos os itens encontrados
    """
    # Extrair dados
    texto_completo = json_data.get("texto_completo", "")
    tables = json_data.get("tables_norm", [])
    page_count = json_data.get("page_count", 1)
    blob_name = json_data.get("blob_name", "documento")
    
    if verbose:
        print("\n" + "="*60)
        print(f"📄 PROCESSANDO: {blob_name}")
        print(f"   Páginas: {page_count}")
        print(f"   Tabelas encontradas: {len(tables)}")
        print("="*60)
    
    # Preparar texto por página (simplificado)
    texto_por_pagina = extrair_texto_por_pagina(texto_completo, page_count)
    
    # ==========================================================================
    # ETAPA 1: SCAN DE PÁGINAS (PRÉ-FILTRO)
    # ==========================================================================
    if verbose:
        print("\n📋 ETAPA 1: Scan de páginas candidatas...")
    
    paginas_candidatas = scan_documento(texto_por_pagina, apenas_fortes=False)
    
    if verbose:
        fortes = [p for p in paginas_candidatas if p.is_forte_candidato]
        print(f"   Páginas analisadas: {len(texto_por_pagina)}")
        print(f"   Candidatas fortes: {len(fortes)}")
        
        for candidato in paginas_candidatas[:3]:
            print_resultado_scan(candidato)
    
    # ==========================================================================
    # ETAPA 2: SCORING DE TABELAS
    # ==========================================================================
    if verbose:
        print("\n\n📊 ETAPA 2: Scoring de tabelas...")
    
    if not tables:
        if verbose:
            print("   ⚠️ Nenhuma tabela encontrada no documento!")
        return ResultadoExtracao(
            itens=[],
            total_itens=0,
            paginas_processadas=[],
            tabelas_processadas=0,
            erros=["Nenhuma tabela encontrada"]
        )
    
    # Adicionar page_number às tabelas se não existir
    for i, table in enumerate(tables):
        if "page_number" not in table:
            table["page_number"] = 1  # Default
        if "table_index" not in table:
            table["table_index"] = i
    
    scores = filtrar_tabelas_candidatas(
        tables=tables,
        texto_por_pagina=texto_por_pagina,
        apenas_fortes=False
    )
    
    tabelas_fortes = [s for s in scores if s.is_forte_candidato]
    
    if verbose:
        print(f"   Tabelas analisadas: {len(tables)}")
        print(f"   Tabelas fortes candidatas: {len(tabelas_fortes)}")
        
        for score in scores[:5]:
            print_score_result(score)
    
    # ==========================================================================
    # ETAPA 3: EXTRAÇÃO DE ITENS
    # ==========================================================================
    if verbose:
        print("\n\n📦 ETAPA 3: Extração de itens...")
    
    resultado = extrair_itens_documento(
        tables=tables,
        scores=scores if tabelas_fortes else None,  # Se não há fortes, tenta todas
        texto_por_pagina=texto_por_pagina
    )
    
    if verbose:
        print_resultado_extracao(resultado)
    
    return resultado


def processar_arquivo(filepath: str, verbose: bool = True) -> Dict:
    """
    Processa arquivo JSON e retorna resultado em formato dict.
    
    Args:
        filepath: Caminho para arquivo JSON parseado
        verbose: Se True, imprime detalhes
    
    Returns:
        Dict com resultado da extração
    """
    json_data = carregar_json_parseado(filepath)
    resultado = processar_documento(json_data, verbose=verbose)
    
    return {
        "arquivo": filepath,
        "total_itens": resultado.total_itens,
        "tabelas_processadas": resultado.tabelas_processadas,
        "paginas_processadas": resultado.paginas_processadas,
        "erros": resultado.erros,
        "itens": [item_to_dict(item) for item in resultado.itens]
    }


def main():
    """Função principal CLI."""
    if len(sys.argv) < 2:
        print("Uso: python main.py <arquivo.json> [--quiet]")
        print("\nExemplo:")
        print("  python main.py documento_parsed.json")
        print("  python main.py documento_parsed.json --quiet")
        sys.exit(1)
    
    filepath = sys.argv[1]
    verbose = "--quiet" not in sys.argv
    
    if not Path(filepath).exists():
        print(f"❌ Arquivo não encontrado: {filepath}")
        sys.exit(1)
    
    try:
        resultado = processar_arquivo(filepath, verbose=verbose)
        
        # Salvar resultado
        output_path = filepath.replace(".json", "_itens.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Resultado salvo em: {output_path}")
        print(f"   Total de itens extraídos: {resultado['total_itens']}")
        
    except Exception as e:
        print(f"❌ Erro ao processar: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
