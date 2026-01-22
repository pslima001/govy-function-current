# govy/extractors/l001_tables_di.py
"""
L001 - Extrator de Locais de Entrega via Tabelas (Document Intelligence)

Este arquivo contém a lógica para extrair locais de entrega de TABELAS
detectadas pelo Azure Document Intelligence.

Versão: 2.0 - 20/01/2026
Correção: Identifica tabelas de escolas/endereços pelo HEADER antes de processar.
          Antes: processava todas as tabelas na ordem e atingia MAX_VALUES com lixo.
          Agora: só processa tabelas que têm colunas "Escola" E "Endereço".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResultList:
    """Resultado da extração de lista de valores."""
    values: List[str]
    evidence: Optional[str]
    score: int


# =============================================================================
# CONFIGURAÇÃO DE REGRAS - EDITE AQUI
# =============================================================================

# Padrões para detectar indicadores de endereço
ADDRESS_HINTS = [
    "rua", "r.", "av.", "av", "avenida", "praça", "praca", "travessa",
    "rodovia", "rod.", "estrada", "km", "bairro", "cep", "nº", "no.",
    "n.", "s/n", "alameda", "largo", "via", "pça"
]

# Termos negativos (indicam que NÃO é local de entrega)
TERMOS_NEGATIVOS = [
    "cnpj", "cpf", "telefone", "tel.", "fax", "e-mail", "email",
    "site", "www", "agesul", "sinapi", "sicro", "composição",
    "unitário", "quantidade", "valor total", "preço", "bdi",
    "placa de obra", "m2", "m³", "inscrição", "razão social"
]

# Tamanho mínimo de texto para considerar como endereço
MIN_ADDRESS_LENGTH = 20

# Máximo de valores a extrair (aumentado de 40 para 100)
MAX_VALUES = 100


# =============================================================================
# REGEX COMPILADOS
# =============================================================================

ADDRESS_HINT_RE = re.compile(
    r"\b(" + "|".join(re.escape(h) for h in ADDRESS_HINTS) + r")\b",
    re.IGNORECASE,
)
CEP_RE = re.compile(r"\b\d{5}-?\d{3}\b")
CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def _norm(s: str) -> str:
    """Normaliza string removendo espaços extras."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _looks_like_address(s: str) -> bool:
    """Verifica se uma string parece ser um endereço válido."""
    if not s:
        return False

    n = _norm(s).lower()

    # Muito curto
    if len(n) < MIN_ADDRESS_LENGTH:
        return False

    # Tem termos negativos
    for neg in TERMOS_NEGATIVOS:
        if neg.lower() in n:
            return False

    # CNPJ sem contexto de endereço (provavelmente dado de empresa)
    if CNPJ_RE.search(n) and not ADDRESS_HINT_RE.search(n):
        return False

    # Precisa ter pelo menos um indicador de endereço ou CEP
    return bool(ADDRESS_HINT_RE.search(n) or CEP_RE.search(n))


def _is_escola_endereco_table(table: Dict) -> Tuple[bool, Optional[int]]:
    """
    Verifica se a tabela tem estrutura de escola/endereço.
    
    Returns:
        Tuple[bool, Optional[int]]: (é_tabela_valida, coluna_endereco)
    """
    cells = table.get("cells", [])
    if not cells:
        return False, None

    # Pegar células da linha 0 (header)
    header_cells = {}
    for cell in cells:
        if int(cell.get("row", 0)) == 0:
            col = int(cell.get("col", 0))
            text = _norm(cell.get("text", "")).lower()
            header_cells[col] = text

    # Verificar se tem "escola" e "endereço" no header
    has_escola = any("escola" in t for t in header_cells.values())
    has_endereco = False
    endereco_col = None

    for col, text in header_cells.items():
        if "endereço" in text or "endereco" in text:
            has_endereco = True
            endereco_col = col
            break

    if has_escola and has_endereco:
        return True, endereco_col

    return False, None


# =============================================================================
# FUNÇÃO PRINCIPAL DE EXTRAÇÃO
# =============================================================================

def extract_l001_from_tables_norm(
    tables_norm: List[Dict],
    max_values: int = MAX_VALUES,
) -> ExtractResultList:
    """
    Extrai locais/endereços de tabelas normalizadas do Azure Document Intelligence.
    
    ESTRATÉGIA v2.0:
    1. Primeiro, identifica APENAS tabelas que têm header com "Escola" E "Endereço"
    2. Depois, extrai endereços apenas da coluna identificada
    3. Isso evita processar tabelas de orçamento/custos que têm "nº" e outros hints
    
    Args:
        tables_norm: Lista de tabelas no formato:
            [{table_index, row_count, column_count, cells: [{row, col, text, ...}]}]
        max_values: Número máximo de valores a extrair
        
    Returns:
        ExtractResultList com valores encontrados
    """
    candidates: List[str] = []
    evidence_parts: List[str] = []
    enderecos_vistos: set = set()

    # PASSO 1: Identificar tabelas de escola/endereço
    escola_tables: List[Tuple[Dict, int]] = []
    for table in (tables_norm or []):
        is_valid, endereco_col = _is_escola_endereco_table(table)
        if is_valid and endereco_col is not None:
            escola_tables.append((table, endereco_col))

    # Se não encontrou tabelas de escola, tenta fallback com todas as tabelas
    if not escola_tables:
        # Fallback: processar todas as tabelas (comportamento antigo)
        for table in (tables_norm or []):
            rows: Dict[int, List[Tuple[int, str]]] = {}
            for cell in table.get("cells", []):
                row_idx = int(cell.get("row", 0))
                col_idx = int(cell.get("col", 0))
                text = _norm(cell.get("text", ""))
                if text:
                    rows.setdefault(row_idx, []).append((col_idx, text))

            for row_idx, cols in sorted(rows.items()):
                cols_sorted = [t for _, t in sorted(cols, key=lambda x: x[0])]
                row_text = " | ".join(cols_sorted)

                if _looks_like_address(row_text):
                    key = _norm(row_text).lower()
                    if key not in enderecos_vistos:
                        enderecos_vistos.add(key)
                        candidates.append(row_text)
                        evidence_parts.append(
                            f"Tabela {table.get('table_index')} linha {row_idx}: {row_text[:100]}"
                        )

                if len(candidates) >= max_values:
                    break
            if len(candidates) >= max_values:
                break
    else:
        # PASSO 2: Processar apenas tabelas de escola/endereço
        for table, endereco_col in escola_tables:
            cells = table.get("cells", [])
            table_idx = table.get("table_index", "?")

            # Agrupar células por linha
            rows: Dict[int, Dict[int, str]] = {}
            for cell in cells:
                row_idx = int(cell.get("row", 0))
                col_idx = int(cell.get("col", 0))
                text = _norm(cell.get("text", ""))
                rows.setdefault(row_idx, {})[col_idx] = text

            # Extrair endereços (pular linha 0 que é header)
            for row_idx in sorted(rows.keys()):
                if row_idx == 0:
                    continue

                cols = rows[row_idx]
                endereco = cols.get(endereco_col, "").strip()

                if endereco and _looks_like_address(endereco):
                    key = _norm(endereco).lower()
                    if key not in enderecos_vistos:
                        enderecos_vistos.add(key)
                        candidates.append(endereco)
                        evidence_parts.append(
                            f"Tabela {table_idx} linha {row_idx}: {endereco[:100]}"
                        )

                if len(candidates) >= max_values:
                    break
            if len(candidates) >= max_values:
                break

    # Montar resultado
    evidence = "\n".join(evidence_parts[:15]) if evidence_parts else None
    score = 85 if candidates else 0

    return ExtractResultList(
        values=candidates,
        evidence=evidence,
        score=score
    )