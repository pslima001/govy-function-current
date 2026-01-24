import re
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class PageScanResult:
    page_num: int
    text: str
    has_table_indicators: bool
    indicators_found: List[str]
    score: float
    is_candidate: bool

ITEM_TABLE_INDICATORS = {
    'headers': [r'\bitem\b', r'\blote\b', r'\bdescri[cç][aã]o\b', r'\bespecifica[cç][aã]o\b',
                r'\bunidade\b', r'\bun\.?\b', r'\bqtd\.?\b', r'\bquantidade\b',
                r'\bvalor\s*unit[aá]rio\b', r'\bvalor\s*total\b', r'\bpre[cç]o\s*unit[aá]rio\b',
                r'\bpre[cç]o\s*total\b', r'\bp\.?\s*unit\.?\b', r'\bp\.?\s*total\.?\b'],
    'sections': [r'termo\s*de\s*refer[eê]ncia', r'anexo\s*[iv]+', r'anexo\s*\d+',
                 r'defini[cç][aã]o\s*do\s*objeto', r'especifica[cç][oõ]es\s*t[eé]cnicas',
                 r'quantidades\s*estimadas'],
    'codes': [r'\bcatmat\b', r'\bcatser\b', r'\bsimpas\b', r'\bc[oó]digo\s*(?:do\s*)?item\b'],
    'values': [r'r\$\s*[\d\.,]+', r'[\d\.,]+\s*(?:real|reais)']
}

INDICATOR_WEIGHTS = {'headers': 2.0, 'sections': 1.5, 'codes': 2.0, 'values': 1.0}

STRONG_CANDIDATE_RULES = [
    (r'valor\s*unit[aá]rio', r'valor\s*total'),
    (r'pre[cç]o\s*unit[aá]rio', r'pre[cç]o\s*total'),
    (r'\bitem\b', r'\bdescri[cç][aã]o\b', r'\bqt[de]'),
]

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Dict[int, str]:
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF nao instalado")
    
    pages_text = {}
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        # Remover caracteres problematicos - CODIGOS REAIS: 8203 (zero width space), etc
        chars_to_remove = {8203, 8204, 8205, 8206, 8207, 8234, 8235, 8236, 8237, 8238, 65279, 160}
        cleaned = []
        for char in text:
            code = ord(char)
            if code in chars_to_remove:
                continue  # Remove completamente
            elif code < 32 and code not in (10, 13, 9):
                continue  # Remove caracteres de controle
            else:
                cleaned.append(char)
        text = ''.join(cleaned)
        text = re.sub(r'  +', ' ', text)
        text = re.sub(r'\n +', '\n', text)
        pages_text[page_num + 1] = text
    doc.close()
    return pages_text

def check_strong_candidate(text: str) -> Tuple[bool, str]:
    text_lower = text.lower()
    for rule in STRONG_CANDIDATE_RULES:
        all_match = True
        for pattern in rule:
            if not re.search(pattern, text_lower, re.IGNORECASE):
                all_match = False
                break
        if all_match:
            return True, f"Regra: {' + '.join(rule)}"
    return False, ""

def scan_page(page_num: int, text: str) -> PageScanResult:
    text_lower = text.lower()
    indicators_found = []
    total_score = 0.0
    for group, patterns in ITEM_TABLE_INDICATORS.items():
        weight = INDICATOR_WEIGHTS[group]
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                indicators_found.append(f"{group}:{pattern}")
                total_score += weight
    is_strong, rule = check_strong_candidate(text)
    if is_strong:
        total_score += 5.0
        indicators_found.append(f"FORTE:{rule}")
    is_candidate = total_score >= 4.0 or is_strong
    return PageScanResult(page_num=page_num, text=text, has_table_indicators=len(indicators_found) > 0,
                          indicators_found=indicators_found, score=total_score, is_candidate=is_candidate)

def scan_pdf_for_item_pages(pdf_bytes: bytes) -> Dict:
    pages_text = extract_text_from_pdf_bytes(pdf_bytes)
    results = []
    candidates = []
    for page_num, text in pages_text.items():
        scan_result = scan_page(page_num, text)
        results.append(scan_result)
        if scan_result.is_candidate:
            candidates.append(scan_result)
    candidates.sort(key=lambda x: x.score, reverse=True)
    return {
        'total_pages': len(pages_text),
        'candidates_count': len(candidates),
        'candidate_pages': [c.page_num for c in candidates],
        'candidates': [{'page': c.page_num, 'score': round(c.score, 2), 'indicators': c.indicators_found,
                        'text_preview': c.text[:500] + '...' if len(c.text) > 500 else c.text} for c in candidates],
        'all_pages_scores': [{'page': r.page_num, 'score': round(r.score, 2), 'is_candidate': r.is_candidate} for r in results]
    }

def extract_pages_as_pdf(pdf_bytes: bytes, pages: List[int]) -> bytes:
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF nao instalado")
    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    dst_doc = fitz.open()
    for page_num in pages:
        if 1 <= page_num <= len(src_doc):
            dst_doc.insert_pdf(src_doc, from_page=page_num-1, to_page=page_num-1)
    pdf_output = dst_doc.tobytes()
    src_doc.close()
    dst_doc.close()
    return pdf_output
