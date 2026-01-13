# src/govy/extractors/l001_tables_di.py
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .l001_locais import ExtractResultList

# Heurística simples para capturar endereços/local de entrega em células de tabela
ADDRESS_HINT_RE = re.compile(
    r"\b(rua|r\.|av\.?|avenida|pra[çc]a|travessa|rodovia|rod\.?|estrada|km|bairro|centro|cep|n[ºo]\.?|s/n)\b",
    re.IGNORECASE,
)
CEP_RE = re.compile(r"\b\d{2}\.?(\d{3})-?(\d{3})\b")
CNPJ_RE = re.compile(r"\b\d{2}\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})\b")

# remove strings obviamente não-endereço
NOISE_RE = re.compile(r"^(?:\s*[-_*•]+\s*|\s*)$")


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _looks_like_address(s: str) -> bool:
    if not s:
        return False
    n = _norm(s).lower()
    if len(n) < 12:
        return False
    if NOISE_RE.match(n):
        return False
    # corta coisas tipo 'CNPJ: ...'
    if CNPJ_RE.search(n) and len(n) < 40:
        return False
    # precisa ter pelo menos um gatilho de logradouro/CEP/indicadores comuns
    return bool(ADDRESS_HINT_RE.search(n) or CEP_RE.search(n))


def extract_l001_from_tables_norm(
    tables_norm: List[Dict],
    max_values: int = 40,
) -> ExtractResultList:
    """
    Extrai possíveis locais/endereço a partir de tabelas normalizadas do Azure DI
    (formato: [{table_index,row_count,column_count,cells:[{row,col,text,...}]}]).
    """
    candidates: List[str] = []
    evidence_parts: List[str] = []

    for tb in tables_norm or []:
        # agrupa por linha
        rows: Dict[int, List[Tuple[int, str]]] = {}
        for cell in tb.get("cells", []):
            r = int(cell.get("row", 0))
            c = int(cell.get("col", 0))
            txt = _norm(cell.get("text", ""))
            if not txt:
                continue
            rows.setdefault(r, []).append((c, txt))

        for r, cols in sorted(rows.items()):
            cols_sorted = [t for _, t in sorted(cols, key=lambda x: x[0])]
            row_text = " | ".join(cols_sorted)
            if _looks_like_address(row_text):
                candidates.append(row_text)
                evidence_parts.append(f"Tabela {tb.get('table_index')} linha {r}: {row_text}")
            else:
                # fallback: testa célula individual (às vezes a linha tem muito ruído)
                for t in cols_sorted:
                    if _looks_like_address(t):
                        candidates.append(t)
                        evidence_parts.append(f"Tabela {tb.get('table_index')} linha {r}: {t}")

            if len(candidates) >= max_values:
                break
        if len(candidates) >= max_values:
            break

    # dedup preservando ordem
    seen = set()
    deduped: List[str] = []
    for v in candidates:
        key = _norm(v).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)

    evidence = "\n".join(evidence_parts[:10]) if evidence_parts else None
    score = 85 if deduped else 0
    return ExtractResultList(values=deduped, evidence=evidence, score=score)
