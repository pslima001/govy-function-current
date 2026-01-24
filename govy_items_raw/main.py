from typing import Dict, List
from .pdf_scanner import scan_pdf_for_item_pages, extract_text_from_pdf_bytes, extract_pages_as_pdf
from .raw_extractor import extract_items_raw, to_dict as extraction_to_dict

def process_pdf_items_raw(pdf_bytes: bytes) -> Dict:
    scan_result = scan_pdf_for_item_pages(pdf_bytes)
    pages_text = extract_text_from_pdf_bytes(pdf_bytes)
    candidate_pages = scan_result['candidate_pages']
    extraction_result = extract_items_raw(pages_text, candidate_pages)
    extraction_dict = extraction_to_dict(extraction_result)
    return {
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

def get_candidate_pages_pdf(pdf_bytes: bytes, pages: List[int] = None) -> bytes:
    if pages is None:
        scan_result = scan_pdf_for_item_pages(pdf_bytes)
        pages = scan_result['candidate_pages']
    if not pages:
        raise ValueError("Nenhuma pagina candidata identificada")
    return extract_pages_as_pdf(pdf_bytes, pages)

def get_pages_text(pdf_bytes: bytes, pages: List[int] = None) -> Dict[int, str]:
    all_pages = extract_text_from_pdf_bytes(pdf_bytes)
    if pages is None:
        return all_pages
    return {p: all_pages[p] for p in pages if p in all_pages}
