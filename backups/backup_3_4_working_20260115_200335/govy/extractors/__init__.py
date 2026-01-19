# govy/extractors/__init__.py
"""
Pacote de Extractors do Govy

Este pacote contém os extractors para cada parâmetro:
- e001_entrega: Prazo de Entrega
- pg001_pagamento: Prazo de Pagamento
- o001_objeto: Objeto da Licitação
- l001_tables_di: Locais de Entrega (via tabelas DI)
- l001_locais: Locais de Entrega (via texto)

Última atualização: 15/01/2026
"""

from .e001_entrega import extract_e001, ExtractResult
from .pg001_pagamento import extract_pg001
from .o001_objeto import extract_o001
from .l001_tables_di import extract_l001_from_tables_norm, ExtractResultList
from .l001_locais import extract_l001

__all__ = [
    "extract_e001",
    "extract_pg001",
    "extract_o001",
    "extract_l001",
    "extract_l001_from_tables_norm",
    "ExtractResult",
    "ExtractResultList",
]
