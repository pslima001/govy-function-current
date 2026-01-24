"""
page_scanner.py - Scan leve de PDFs para identificar páginas candidatas.

Este módulo faz uma análise preliminar do documento ANTES do parse completo
do Azure Document Intelligence, identificando quais páginas têm maior
probabilidade de conter tabelas de itens.

Objetivo: Reduzir custo processando apenas páginas relevantes.
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from .constants import (
    TODOS_INDICADORES,
    SECOES_TERMO_REFERENCIA,
    COMBINACOES_FORTE_CANDIDATO,
    REGEX_VALOR_MONETARIO,
    MIN_INDICADORES_TABELA,
    MIN_INDICADORES_COM_TR,
)


@dataclass
class PageCandidate:
    """Resultado da análise de uma página."""
    page_number: int
    score: float
    is_forte_candidato: bool
    indicadores_encontrados: List[str]
    tem_valor_unit_total: bool
    dentro_termo_referencia: bool
    tem_valores_monetarios: bool
    tem_estrutura_tabela: bool
    motivo: str


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação."""
    if not text:
        return ""
    text = text.lower().strip()
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


def detectar_estrutura_tabular(texto: str) -> bool:
    """
    Detecta se o texto tem estrutura que sugere tabela.
    Heurísticas:
    - Múltiplas linhas com padrão similar
    - Presença de delimitadores (|, tabs)
    - Sequência numérica (1, 2, 3...)
    - Alinhamento de valores
    """
    linhas = texto.split('\n')
    
    # Verificar se há linhas com múltiplos valores numéricos alinhados
    linhas_com_numeros = 0
    for linha in linhas:
        # Contar números na linha
        numeros = re.findall(r'\d+(?:[.,]\d+)?', linha)
        if len(numeros) >= 2:
            linhas_com_numeros += 1
    
    # Se muitas linhas têm múltiplos números, provavelmente é tabela
    if linhas_com_numeros >= 3:
        return True
    
    # Verificar sequência de itens (1, 2, 3...)
    sequencia = re.findall(r'^\s*(\d+)\s*[.\-\)]', texto, re.MULTILINE)
    if len(sequencia) >= 3:
        return True
    
    # Verificar padrão de delimitadores
    if texto.count('|') >= 5 or texto.count('\t') >= 5:
        return True
    
    return False


def contar_indicadores_texto(texto: str) -> Tuple[int, List[str]]:
    """Conta indicadores no texto."""
    texto_norm = normalize_text(texto)
    encontrados = []
    
    for indicador in TODOS_INDICADORES:
        indicador_norm = normalize_text(indicador)
        if indicador_norm in texto_norm:
            encontrados.append(indicador)
    
    return len(encontrados), encontrados


def verificar_combinacao_valor(texto: str) -> bool:
    """Verifica se tem Valor Unitário + Valor Total juntos."""
    texto_norm = normalize_text(texto)
    
    for unit, total in COMBINACOES_FORTE_CANDIDATO:
        if normalize_text(unit) in texto_norm and normalize_text(total) in texto_norm:
            return True
    return False


def verificar_termo_referencia(texto: str) -> bool:
    """Verifica se está em contexto de Termo de Referência."""
    texto_norm = normalize_text(texto)
    
    for secao in SECOES_TERMO_REFERENCIA:
        if normalize_text(secao) in texto_norm:
            return True
    return False


def analisar_pagina(
    texto_pagina: str,
    page_number: int,
    contexto_documento: Optional[str] = None
) -> PageCandidate:
    """
    Analisa uma página individual para determinar se é candidata.
    
    Args:
        texto_pagina: Texto extraído da página (pode ser OCR básico)
        page_number: Número da página
        contexto_documento: Texto das páginas anteriores para contexto
    
    Returns:
        PageCandidate com análise completa
    """
    # Análises básicas
    num_indicadores, indicadores = contar_indicadores_texto(texto_pagina)
    tem_valor_unit_total = verificar_combinacao_valor(texto_pagina)
    
    # Verificar TR considerando contexto (páginas anteriores podem indicar início do TR)
    contexto_completo = (contexto_documento or "") + " " + texto_pagina
    dentro_tr = verificar_termo_referencia(contexto_completo)
    
    tem_valores = bool(REGEX_VALOR_MONETARIO.search(texto_pagina))
    tem_estrutura = detectar_estrutura_tabular(texto_pagina)
    
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
    
    # Regra 2: Estrutura tabular + ≥3 indicadores
    elif tem_estrutura and num_indicadores >= MIN_INDICADORES_TABELA:
        is_forte = True
        motivo = f"Regra 2: Estrutura tabular + {num_indicadores} indicadores"
        score = 0.9
    
    # Regra 3: Dentro de TR + estrutura + ≥2 indicadores
    elif dentro_tr and tem_estrutura and num_indicadores >= MIN_INDICADORES_COM_TR:
        is_forte = True
        motivo = f"Regra 3: TR + estrutura + {num_indicadores} indicadores"
        score = 0.85
    
    # Regra 4: Muitos indicadores mesmo sem estrutura clara
    elif num_indicadores >= 4:
        is_forte = True
        motivo = f"Regra 4: {num_indicadores} indicadores (≥4)"
        score = 0.8
    
    # Candidato médio
    elif num_indicadores >= 2 and (tem_valores or tem_estrutura):
        motivo = f"Candidato médio: {num_indicadores} indicadores"
        score = 0.5
    
    # Candidato fraco
    elif num_indicadores >= 1:
        motivo = f"Candidato fraco: {num_indicadores} indicador(es)"
        score = 0.2
    
    else:
        motivo = "Não é candidato"
        score = 0.0
    
    # Bônus
    if tem_valores and score > 0 and score < 1.0:
        score += 0.05
    
    return PageCandidate(
        page_number=page_number,
        score=min(1.0, score),
        is_forte_candidato=is_forte,
        indicadores_encontrados=indicadores,
        tem_valor_unit_total=tem_valor_unit_total,
        dentro_termo_referencia=dentro_tr,
        tem_valores_monetarios=tem_valores,
        tem_estrutura_tabela=tem_estrutura,
        motivo=motivo,
    )


def scan_documento(
    texto_por_pagina: Dict[int, str],
    apenas_fortes: bool = True
) -> List[PageCandidate]:
    """
    Faz scan completo do documento para identificar páginas candidatas.
    
    Args:
        texto_por_pagina: Dicionário {número_página: texto}
        apenas_fortes: Se True, retorna apenas FORTES CANDIDATOS
    
    Returns:
        Lista de PageCandidate ordenada por score
    """
    resultados = []
    contexto_acumulado = ""
    
    # Processar páginas em ordem
    paginas_ordenadas = sorted(texto_por_pagina.keys())
    
    for page_num in paginas_ordenadas:
        texto = texto_por_pagina[page_num]
        
        # Analisar página com contexto das anteriores
        resultado = analisar_pagina(
            texto_pagina=texto,
            page_number=page_num,
            contexto_documento=contexto_acumulado[-5000:]  # Últimos 5000 chars
        )
        
        # Acumular contexto
        contexto_acumulado += " " + texto
        
        # Filtrar
        if apenas_fortes:
            if resultado.is_forte_candidato:
                resultados.append(resultado)
        else:
            if resultado.score > 0:
                resultados.append(resultado)
    
    # Ordenar por score
    resultados.sort(key=lambda x: x.score, reverse=True)
    
    return resultados


def identificar_paginas_para_parse(
    texto_por_pagina: Dict[int, str],
    max_paginas: int = 50
) -> List[int]:
    """
    Retorna lista de números de página que devem ser enviadas para parse completo.
    
    Args:
        texto_por_pagina: Dicionário {número_página: texto}
        max_paginas: Máximo de páginas a retornar
    
    Returns:
        Lista de números de página ordenados
    """
    candidatos = scan_documento(texto_por_pagina, apenas_fortes=True)
    
    # Pegar páginas dos candidatos fortes
    paginas = set()
    for candidato in candidatos[:max_paginas]:
        paginas.add(candidato.page_number)
        # Adicionar página anterior e posterior (contexto)
        if candidato.page_number > 1:
            paginas.add(candidato.page_number - 1)
        paginas.add(candidato.page_number + 1)
    
    return sorted(list(paginas))


def print_resultado_scan(candidato: PageCandidate) -> None:
    """Imprime resultado do scan de forma legível."""
    status = "✅ FORTE" if candidato.is_forte_candidato else "⚪ Fraco"
    print(f"\n{status} | Página {candidato.page_number}")
    print(f"  Score: {candidato.score:.2f}")
    print(f"  Motivo: {candidato.motivo}")
    print(f"  Indicadores: {', '.join(candidato.indicadores_encontrados) or 'Nenhum'}")
    print(f"  Valor Unit+Total: {'Sim' if candidato.tem_valor_unit_total else 'Não'}")
    print(f"  Dentro de TR: {'Sim' if candidato.dentro_termo_referencia else 'Não'}")
    print(f"  Estrutura tabular: {'Sim' if candidato.tem_estrutura_tabela else 'Não'}")
    print(f"  Valores R$: {'Sim' if candidato.tem_valores_monetarios else 'Não'}")


if __name__ == "__main__":
    # Teste com exemplo
    texto_teste = """
    TERMO DE REFERÊNCIA
    
    1. DO OBJETO
    
    Registro de Preços para aquisição de medicamentos.
    
    Item    Descrição           Qtde    Un.     Valor Unitário  Valor Total
    1       Paracetamol 500mg   10000   CP      R$ 0,15         R$ 1.500,00
    2       Dipirona 500mg      5000    CP      R$ 0,20         R$ 1.000,00
    3       Amoxicilina 500mg   2000    CP      R$ 0,50         R$ 1.000,00
    """
    
    resultado = analisar_pagina(texto_teste, page_number=15)
    print_resultado_scan(resultado)
