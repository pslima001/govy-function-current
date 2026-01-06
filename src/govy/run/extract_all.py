# src/govy/run/extract_all.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple

from govy.extractors.e001_entrega import extract_e001
from govy.extractors.o001_objeto import extract_o001
from govy.extractors.pg001_pagamento import extract_pg001
from govy.extractors.l001_locais import extract_l001, ExtractResultList
from govy.extractors.l001_anexo_texto import extract_l001_many_locations_from_text
from govy.extractors.l001_tables_di import extract_l001_from_tables_norm


def _to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    # fallback
    return str(obj)


def extract_all_params(
    content_clean: str,
    tables_norm: Optional[List[Dict[str, Any]]] = None,
    *,
    include_debug: bool = False,
) -> Dict[str, Any]:
    """
    Executa todos os parâmetros baseados em:
      - content_clean: texto já limpo (sem header/footer)
      - tables_norm: tabelas normalizadas (Azure DI prebuilt-layout)

    Retorna dicionário JSON-friendly.
    """

    out: Dict[str, Any] = {}

    # ---- parâmetros principais ----
    out["O001"] = _to_dict(extract_o001(content_clean))
    out["E001"] = _to_dict(extract_e001(content_clean))
    out["PG001"] = _to_dict(extract_pg001(content_clean))

    # ---- L001: combina 3 fontes (texto principal + anexo + tabelas) ----
    l_text = extract_l001(content_clean)
    l_anexo = extract_l001_many_locations_from_text(content_clean)
    l_tabs = extract_l001_from_tables_norm(tables_norm or [])

    # merge de values com dedup
    merged: List[str] = []
    seen = set()
    for src in (l_text, l_anexo, l_tabs):
        for v in (src.values or []):
            key = (v or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(v.strip())

    # evidência: prioriza fonte mais forte
    evidence = l_text.evidence or l_anexo.evidence or l_tabs.evidence
    score = max(l_text.score, l_anexo.score, l_tabs.score) if merged else 0

    out["L001"] = _to_dict(ExtractResultList(values=merged, evidence=evidence, score=score))

    if include_debug:
        out["_debug"] = {
            "l001_sources": {
                "text": _to_dict(l_text),
                "anexo": _to_dict(l_anexo),
                "tables": _to_dict(l_tabs),
            }
        }

    return out
