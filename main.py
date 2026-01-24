"""
Main - Integração do módulo de extração raw de itens
Camada 1 - Custo: ZERO
"""

from typing import Dict, List, Optional
from .pdf_scanner import (
    scan_pdf_for_item_pages,
    extract_text_from_pdf_bytes,
    extract_pages_as_pdf
)
from .raw_extractor import (
    extract_items_raw,
    to_dict as extraction_to_dict
)


def process_pdf_items_raw(pdf_bytes: bytes) -> Dict:
    """
    Processa PDF para extração de itens usando apenas Camada 1 (código).
    
    Fluxo:
    1. Extrai texto de todas as páginas (PyMuPDF)
    2. Identifica páginas candidatas
    3. Tenta extração direta via regex
    4. Calcula confiança
    5. Retorna resultado + recomendação (usar direto ou enviar para DI)
    
    Returns:
        Dict com:
        - scan_result: Resultado do scan de páginas
        - extraction_result: Itens extraídos + confiança
        - recommendation: 'USAR_DIRETO' ou 'ENVIAR_PARA_DI'
        - candidate_pages_pdf: Se precisar, bytes do PDF com só as páginas candidatas
    """
    # 1. Scan para identificar páginas candidatas
    scan_result = scan_pdf_for_item_pages(pdf_bytes)
    
    # 2. Extrair texto bruto
    pages_text = extract_text_from_pdf_bytes(pdf_bytes)
    
    # 3. Tentar extração direta das páginas candidatas
    candidate_pages = scan_result['candidate_pages']
    extraction_result = extract_items_raw(pages_text, candidate_pages)
    
    # 4. Converter para dict
    extraction_dict = extraction_to_dict(extraction_result)
    
    # 5. Montar resultado final
    result = {
        'scan': {
            'total_pages': scan_result['total_pages'],
            'candidates_count': scan_result['candidates_count'],
            'candidate_pages': candidate_pages,
            'candidates_detail': scan_result['candidates']
        },
        'extraction': extraction_dict,
        'recommendation': extraction_dict['recommendation'],
        'summary': {
            'pages_scanned': scan_result['total_pages'],
            'pages_with_items': scan_result['candidates_count'],
            'items_found': extraction_dict['total_items'],
            'confidence': extraction_dict['confidence_percent'],
            'needs_di': extraction_dict['needs_di']
        }
    }
    
    return result


def get_candidate_pages_pdf(pdf_bytes: bytes, pages: List[int] = None) -> bytes:
    """
    Extrai apenas as páginas candidatas como novo PDF.
    
    Args:
        pdf_bytes: PDF original
        pages: Lista de páginas (se None, escaneia automaticamente)
        
    Returns:
        Bytes do PDF com apenas as páginas candidatas
    """
    if pages is None:
        scan_result = scan_pdf_for_item_pages(pdf_bytes)
        pages = scan_result['candidate_pages']
    
    if not pages:
        raise ValueError("Nenhuma página candidata identificada")
    
    return extract_pages_as_pdf(pdf_bytes, pages)


def get_pages_text(pdf_bytes: bytes, pages: List[int] = None) -> Dict[int, str]:
    """
    Retorna texto das páginas especificadas.
    
    Args:
        pdf_bytes: PDF original  
        pages: Lista de páginas (se None, retorna todas)
        
    Returns:
        Dict {page_num: text}
    """
    all_pages = extract_text_from_pdf_bytes(pdf_bytes)
    
    if pages is None:
        return all_pages
    
    return {p: all_pages[p] for p in pages if p in all_pages}
