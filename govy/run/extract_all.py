# govy/run/extract_all.py
"""
Engine de extração que orquestra todos os extractors.
"""
from __future__ import annotations
from typing import Any, Dict


def extract_all_params(
    content_clean: str,
    tables_norm: list,
    include_debug: bool = False
) -> Dict[str, Any]:
    """
    Executa todos os extractors e retorna resultados consolidados.
    Keys usam IDs curtos (e001, l001, o001, pg001) para compatibilidade com frontend.
    """
    results: Dict[str, Any] = {}
    
    try:
        from govy.extractors.o001_objeto import extract_o001
        from govy.extractors.e001_entrega import extract_e001
        from govy.extractors.pg001_pagamento import extract_pg001
        from govy.extractors.l001_locais import extract_l001
        from govy.extractors.l001_tables_di import extract_l001_from_tables_norm
    except ImportError as e:
        return {"_error": f"Import error: {e}"}
    
    # O001 - Objeto da licitacao
    try:
        r = extract_o001(content_clean)
        results["o001"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["o001"] = {
            "value": None, "evidence": None, "score": 0,
            "status": "error", "error": str(e) if include_debug else None
        }
    
    # E001 - Prazo de entrega
    try:
        r = extract_e001(content_clean)
        results["e001"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["e001"] = {
            "value": None, "evidence": None, "score": 0,
            "status": "error", "error": str(e) if include_debug else None
        }
    
    # PG001 - Prazo de pagamento
    try:
        r = extract_pg001(content_clean)
        results["pg001"] = {
            "value": r.value,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.value else "not_found"
        }
    except Exception as e:
        results["pg001"] = {
            "value": None, "evidence": None, "score": 0,
            "status": "error", "error": str(e) if include_debug else None
        }
    
    # L001 - Locais de entrega
    try:
        r = extract_l001(content_clean)
        results["l001"] = {
            "value": r.values[0] if r.values else None,
            "values": r.values,
            "evidence": r.evidence,
            "score": r.score,
            "status": "found" if r.values else "not_found"
        }
    except Exception as e:
        results["l001"] = {
            "value": None, "values": [], "evidence": None, "score": 0,
            "status": "error", "error": str(e) if include_debug else None
        }
    
    # L001 - Complementar com tabelas
    if tables_norm:
        try:
            r = extract_l001_from_tables_norm(tables_norm)
            if r.values:
                existing = results.get("l001", {})
                existing_values = existing.get("values", [])
                merged_values = list(dict.fromkeys(existing_values + r.values))
                results["l001"] = {
                    "value": merged_values[0] if merged_values else None,
                    "values": merged_values,
                    "evidence": existing.get("evidence") or r.evidence,
                    "score": max(existing.get("score", 0), r.score),
                    "status": "found" if merged_values else "not_found"
                }
        except Exception as e:
            if include_debug and "l001" in results:
                results["l001"]["_tables_error"] = str(e)
    
    return results
