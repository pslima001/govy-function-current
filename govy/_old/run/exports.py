# src/govy/run/exports.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ExportResult:
    total: int
    shown: List[str]
    file_path: Optional[str]


def export_locations_with_cap(
    values: List[str],
    cap: int = 20,
    prefix: str = "locations"
) -> ExportResult:
    """
    Exporta lista de locais com limite de exibição.
    
    Se houver mais locais que o cap, salva todos em arquivo e mostra apenas os primeiros.
    
    Args:
        values: Lista de locais encontrados
        cap: Número máximo de locais para mostrar no console
        prefix: Prefixo para o nome do arquivo de exportação
    
    Returns:
        ExportResult com total, shown (primeiros cap itens) e file_path (se houver mais que cap)
    """
    total = len(values)
    shown = values[:cap] if total > cap else values
    
    file_path = None
    if total > cap:
        # Salva todos os locais em arquivo
        Path("runs").mkdir(exist_ok=True)
        file_path = f"runs/{prefix}_all.txt"
        Path(file_path).write_text("\n".join(values), encoding="utf-8")
    
    return ExportResult(
        total=total,
        shown=shown,
        file_path=file_path
    )







