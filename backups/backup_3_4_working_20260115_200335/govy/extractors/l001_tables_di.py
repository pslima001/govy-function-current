# govy/extractors/l001_tables_di.py
"""
L001 - Extrator de Locais de Entrega via Tabelas (Document Intelligence)

Este arquivo contém a lógica para extrair locais de entrega de TABELAS
detectadas pelo Azure Document Intelligence.

Última atualização: 15/01/2026
Responsável pela edição de regras: ChatGPT 5.2
Responsável pelo deploy: Claude
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

# Padrão para detectar indicadores de endereço
ADDRESS_HINTS = [
    "rua",
    "r.",
    "av.",
    "av",
    "avenida",
    "praça",
    "praca",
    "travessa",
    "rodovia",
    "rod.",
    "estrada",
    "km",
    "bairro",
    "centro",
    "cep",
    "nº",
    "no.",
    "n.",
    "s/n",
]

# Termos negativos (indicam que NÃO é local de entrega)
TERMOS_NEGATIVOS = [
    "cnpj",
    "cpf",
    "telefone",
    "tel.",
    "fax",
    "e-mail",
    "email",
    "site",
    "www",
]

# Tamanho mínimo de texto para considerar como endereço
MIN_ADDRESS_LENGTH = 12

# Máximo de valores a extrair
MAX_VALUES = 40

# =============================================================================
# FUNÇÕES DE EXTRAÇÃO - NÃO EDITE ABAIXO DESTA LINHA
# =============================================================================

# Regex compilados
ADDRESS_HINT_RE = re.compile(
    r"\b(" + "|".join(re.escape(h) for h in ADDRESS_HINTS) + r")\b",
    re.IGNORECASE,
)
CEP_RE = re.compile(r"\b\d{2}\.?(\d{3})-?(\d{3})\b")
CNPJ_RE = re.compile(r"\b\d{2}\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})\b")
NOISE_RE = re.compile(r"^(?:\s*[-_*•]+\s*|\s*)$")


def _norm(s: str) -> str:
    """Normaliza string removendo espaços extras."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _looks_like_address(s: str) -> bool:
    """Verifica se uma string parece ser um endereço."""
    if not s:
        return False
    
    n = _norm(s).lower()
    
    # Muito curto
    if len(n) < MIN_ADDRESS_LENGTH:
        return False
    
    # Só caracteres de formatação
    if NOISE_RE.match(n):
        return False
    
    # CNPJ sem contexto de endereço
    if CNPJ_RE.search(n) and len(n) < 40:
        return False
    
    # Tem termos negativos
    for neg in TERMOS_NEGATIVOS:
        if neg.lower() in n:
            return False
    
    # Precisa ter pelo menos um indicador de endereço ou CEP
    return bool(ADDRESS_HINT_RE.search(n) or CEP_RE.search(n))


def extract_l001_from_tables_norm(
    tables_norm: List[Dict],
    max_values: int = MAX_VALUES,
) -> ExtractResultList:
    """
    Extrai locais/endereços de tabelas normalizadas do Azure Document Intelligence.
    
    Args:
        tables_norm: Lista de tabelas no formato:
            [{table_index, row_count, column_count, cells: [{row, col, text, ...}]}]
        max_values: Número máximo de valores a extrair
        
    Returns:
        ExtractResultList com valores encontrados
    """
    candidates: List[str] = []
    evidence_parts: List[str] = []

    for table in tables_norm or []:
        # Agrupar células por linha
        rows: Dict[int, List[Tuple[int, str]]] = {}
        
        for cell in table.get("cells", []):
            row_idx = int(cell.get("row", 0))
            col_idx = int(cell.get("col", 0))
            text = _norm(cell.get("text", ""))
            
            if not text:
                continue
                
            rows.setdefault(row_idx, []).append((col_idx, text))

        # Processar cada linha
        for row_idx, cols in sorted(rows.items()):
            # Ordenar colunas e juntar texto
            cols_sorted = [t for _, t in sorted(cols, key=lambda x: x[0])]
            row_text = " | ".join(cols_sorted)
            
            # Verificar se a linha inteira parece endereço
            if _looks_like_address(row_text):
                candidates.append(row_text)
                evidence_parts.append(
                    f"Tabela {table.get('table_index')} linha {row_idx}: {row_text}"
                )
            else:
                # Fallback: testar células individuais
                for cell_text in cols_sorted:
                    if _looks_like_address(cell_text):
                        candidates.append(cell_text)
                        evidence_parts.append(
                            f"Tabela {table.get('table_index')} linha {row_idx}: {cell_text}"
                        )

            # Limite de valores
            if len(candidates) >= max_values:
                break
                
        if len(candidates) >= max_values:
            break

    # Deduplicar preservando ordem
    seen = set()
    deduped: List[str] = []
    
    for value in candidates:
        key = _norm(value).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)

    # Montar resultado
    evidence = "\n".join(evidence_parts[:10]) if evidence_parts else None
    score = 85 if deduped else 0
    
    return ExtractResultList(
        values=deduped,
        evidence=evidence,
        score=score
    )
