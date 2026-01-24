"""
GOVY Items Raw Extractor
Camada 1 - Extração via código (PyMuPDF + Regex)
Custo: ZERO
"""

from .main import (
    process_pdf_items_raw,
    get_candidate_pages_pdf,
    get_pages_text
)

from .pdf_scanner import (
    scan_pdf_for_item_pages,
    extract_text_from_pdf_bytes,
    extract_pages_as_pdf
)

from .raw_extractor import (
    extract_items_raw,
    to_dict
)

__all__ = [
    'process_pdf_items_raw',
    'get_candidate_pages_pdf', 
    'get_pages_text',
    'scan_pdf_for_item_pages',
    'extract_text_from_pdf_bytes',
    'extract_pages_as_pdf',
    'extract_items_raw',
    'to_dict'
]

__version__ = '1.0.0'
