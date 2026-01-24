"""
PDF Scanner - Extrai texto bruto via PyMuPDF (Camada 1)
Custo: ZERO
"""

import io
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PageScanResult:
    """Resultado do scan de uma página"""
    page_num: int
    text: str
    has_table_indicators: bool
    indicators_found: List[str]
    score: float
    is_candidate: bool


# Indicadores de tabela de itens
ITEM_TABLE_INDICATORS = {
    # Grupo A - Headers de coluna (peso alto)
    'headers': [
        r'\bitem\b',
        r'\blote\b',
        r'\bdescri[cç][aã]o\b',
        r'\bespecifica[cç][aã]o\b',
        r'\bunidade\b',
        r'\bun\.?\b',
        r'\bqtd\.?\b',
        r'\bquantidade\b',
        r'\bvalor\s*unit[aá]rio\b',
        r'\bvalor\s*total\b',
        r'\bpre[cç]o\s*unit[aá]rio\b',
        r'\bpre[cç]o\s*total\b',
        r'\bp\.?\s*unit\.?\b',
        r'\bp\.?\s*total\.?\b',
    ],
    # Grupo B - Contexto de seção (peso médio)
    'sections': [
        r'termo\s*de\s*refer[eê]ncia',
        r'anexo\s*[iv]+',
        r'anexo\s*\d+',
        r'defini[cç][aã]o\s*do\s*objeto',
        r'especifica[cç][oõ]es\s*t[eé]cnicas',
        r'quantidades\s*estimadas',
    ],
    # Grupo C - Códigos específicos (peso alto)
    'codes': [
        r'\bcatmat\b',
        r'\bcatser\b',
        r'\bsimpas\b',
        r'\bc[oó]digo\s*(?:do\s*)?item\b',
    ],
    # Grupo D - Valores monetários (peso médio)
    'values': [
        r'r\$\s*[\d\.,]+',
        r'[\d\.,]+\s*(?:real|reais)',
    ]
}

# Pesos para cada grupo
INDICATOR_WEIGHTS = {
    'headers': 2.0,
    'sections': 1.5,
    'codes': 2.0,
    'values': 1.0
}

# Combinações que indicam FORTE candidato
STRONG_CANDIDATE_RULES = [
    # Regra 1: "Valor Unitário" + "Valor Total" juntos
    (r'valor\s*unit[aá]rio', r'valor\s*total'),
    (r'pre[cç]o\s*unit[aá]rio', r'pre[cç]o\s*total'),
    (r'p\.?\s*unit\.?', r'p\.?\s*total\.?'),
    # Regra 2: Item + Descrição + Quantidade
    (r'\bitem\b', r'\bdescri[cç][aã]o\b', r'\bqt[de]'),
    # Regra 3: Lote + Item + Valor
    (r'\blote\b', r'\bitem\b', r'\bvalor'),
]


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Dict[int, str]:
    """
    Extrai texto de todas as páginas do PDF usando PyMuPDF.
    
    Args:
        pdf_bytes: Bytes do arquivo PDF
        
    Returns:
        Dict com {page_num: text} para cada página
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF não instalado. Execute: pip install pymupdf")
    
    pages_text = {}
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages_text[page_num + 1] = text  # 1-indexed
    doc.close()
    
    return pages_text


def check_strong_candidate(text: str) -> Tuple[bool, str]:
    """
    Verifica se a página é um FORTE candidato baseado nas regras.
    
    Returns:
        (is_strong, rule_matched)
    """
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
    """
    Analisa uma página e calcula score de candidatura.
    """
    text_lower = text.lower()
    indicators_found = []
    total_score = 0.0
    
    # Verificar cada grupo de indicadores
    for group, patterns in ITEM_TABLE_INDICATORS.items():
        weight = INDICATOR_WEIGHTS[group]
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                indicators_found.append(f"{group}:{pattern}")
                total_score += weight
    
    # Verificar regras de FORTE candidato
    is_strong, rule = check_strong_candidate(text)
    if is_strong:
        total_score += 5.0  # Bonus para forte candidato
        indicators_found.append(f"FORTE:{rule}")
    
    # Determinar se é candidato (threshold = 4.0)
    is_candidate = total_score >= 4.0 or is_strong
    
    return PageScanResult(
        page_num=page_num,
        text=text,
        has_table_indicators=len(indicators_found) > 0,
        indicators_found=indicators_found,
        score=total_score,
        is_candidate=is_candidate
    )


def scan_pdf_for_item_pages(pdf_bytes: bytes) -> Dict:
    """
    Escaneia PDF e identifica páginas candidatas para extração de itens.
    
    Returns:
        Dict com resultados do scan
    """
    # Extrair texto de todas as páginas
    pages_text = extract_text_from_pdf_bytes(pdf_bytes)
    
    # Escanear cada página
    results = []
    candidates = []
    
    for page_num, text in pages_text.items():
        scan_result = scan_page(page_num, text)
        results.append(scan_result)
        if scan_result.is_candidate:
            candidates.append(scan_result)
    
    # Ordenar candidatos por score
    candidates.sort(key=lambda x: x.score, reverse=True)
    
    return {
        'total_pages': len(pages_text),
        'candidates_count': len(candidates),
        'candidate_pages': [c.page_num for c in candidates],
        'candidates': [
            {
                'page': c.page_num,
                'score': round(c.score, 2),
                'indicators': c.indicators_found,
                'text_preview': c.text[:500] + '...' if len(c.text) > 500 else c.text
            }
            for c in candidates
        ],
        'all_pages_scores': [
            {'page': r.page_num, 'score': round(r.score, 2), 'is_candidate': r.is_candidate}
            for r in results
        ]
    }


def extract_pages_as_pdf(pdf_bytes: bytes, pages: List[int]) -> bytes:
    """
    Extrai páginas específicas e retorna como novo PDF.
    
    Args:
        pdf_bytes: PDF original
        pages: Lista de páginas a extrair (1-indexed)
        
    Returns:
        Bytes do novo PDF com apenas as páginas selecionadas
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF não instalado")
    
    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    dst_doc = fitz.open()
    
    for page_num in pages:
        if 1 <= page_num <= len(src_doc):
            dst_doc.insert_pdf(src_doc, from_page=page_num-1, to_page=page_num-1)
    
    pdf_output = dst_doc.tobytes()
    
    src_doc.close()
    dst_doc.close()
    
    return pdf_output


if __name__ == "__main__":
    # Teste local
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'rb') as f:
            pdf_bytes = f.read()
        
        result = scan_pdf_for_item_pages(pdf_bytes)
        print(f"Total páginas: {result['total_pages']}")
        print(f"Candidatas: {result['candidates_count']}")
        print(f"Páginas: {result['candidate_pages']}")
        
        for c in result['candidates'][:5]:
            print(f"\n--- Página {c['page']} (score: {c['score']}) ---")
            print(f"Indicadores: {c['indicators']}")
            print(f"Preview: {c['text_preview'][:200]}...")
