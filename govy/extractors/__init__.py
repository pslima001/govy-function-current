# govy/extractors/__init__.py
"""
Pacote de Extractors do Govy
VERSAO 2.0 - Inclui funcoes _multi para TOP 3 candidatos
Ultima atualizacao: 21/01/2026
"""
from .e001_entrega import extract_e001, extract_e001_multi, ExtractResult
from .pg001_pagamento import extract_pg001, extract_pg001_multi
from .o001_objeto import extract_o001, extract_o001_multi
from .l001_tables_di import extract_l001_from_tables_norm, ExtractResultList
from .l001_locais import extract_l001

__all__ = [
    "extract_e001",
    "extract_e001_multi",
    "extract_pg001",
    "extract_pg001_multi",
    "extract_o001",
    "extract_o001_multi",
    "extract_l001",
    "extract_l001_from_tables_norm",
    "ExtractResult",
    "ExtractResultList",
]