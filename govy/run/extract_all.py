# govy/run/extract_all.py
"""
Engine de extração que orquestra todos os extractors.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from dataclasses import asdict


def extract_all_params(
    content_clean: str,
    tables_norm: list,
    include_debug: bool = False
) -> Dict[str, Any]:
    """
    Executa todos os extractors e retorna resultados consolidados.
    
    Args:
        content_clean: Texto limpo do documento (sem headers/footers)
        tables_norm: Lista de tabelas normalizadas do Document Intelligence
        include_debug: Se True, inclui informações de debug
    
    Returns:
        Dict com resultados de cada extractor no formato:
        {
            "o001_objeto": {"value": "...", "evidence": "...", "score": N, "status": "found|not_found"},
            "e001_entrega": {...},
            ...
        }
    """
    results: Dict[str, Any] = {}
    
    # Import dos extractors (lazy para evitar erros de import circular)
    try:
        from govy.extractors.o001_objeto import extract_o001
        from govy.extractors.e001_entrega import extract_e001
        from govy.extractors.pg001_pagamento import extract_pg001
        from govy.extractors.l001_locais import extract_l001
        from govy.extractors.l001_tables_di import extract_l001_from_tables_norm
    except ImportError as e:
        return {"_error": f"Import error: {e}"}
    
    # O001 - Objeto da licitação
    try:
        r = extract_o001(content_clean)
        results["o001_objeto"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["o001_objeto"] = {
            "value": None,
            "evidence": None,
            "score": 0,
            "status": "error",
            "error": str(e) if include_debug else None
        }
    
    # E001 - Prazo de entrega
    try:
        r = extract_e001(content_clean)
        results["e001_entrega"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["e001_entrega"] = {
            "value": None,
            "evidence": None,
            "score": 0,
            "status": "error",
            "error": str(e) if include_debug else None
        }
    
    # PG001 - Prazo de pagamento
    try:
        r = extract_pg001(content_clean)
        results["pg001_pagamento"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["pg001_pagamento"] = {
            "value": None,
            "evidence": None,
            "score": 0,
            "status": "error",
            "error": str(e) if include_debug else None
        }
    
    # L001 - Locais de entrega (texto)
    try:
        r = extract_l001(content_clean)
        # ExtractResultList tem .values (lista) ao invés de .value
        results["l001_locais"] = {
            "value": r.values[0] if r.values else None,
            "values": r.values,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.values else "not_found"
        }
    except Exception as e:
        results["l001_locais"] = {
            "value": None,
            "values": [],
            "evidence": None,
            "score": 0,
            "status": "error",
            "error": str(e) if include_debug else None
        }
    
    # L001 - Locais de entrega (tabelas) - complementar
    if tables_norm:
        try:
            r = extract_l001_from_tables_norm(tables_norm)
            if r.values:
                # Merge com resultados do texto se houver
                existing = results.get("l001_locais", {})
                existing_values = existing.get("values", [])
                merged_values = list(dict.fromkeys(existing_values + r.values))  # dedup preservando ordem
                results["l001_locais"] = {
                    "value": merged_values[0] if merged_values else None,
                    "values": merged_values,
                    "evidence": existing.get("evidence") or r.evidence,
                    "score": max(existing.get("score", 0), r.score),
                    "status": "found" if merged_values else "not_found"
                }
        except Exception as e:
            if include_debug:
                results["l001_locais"]["_tables_error"] = str(e)
    
    return results
