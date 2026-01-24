import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

@dataclass
class ExtractedItem:
    numero: str
    descricao: str
    unidade: Optional[str] = None
    quantidade: Optional[str] = None
    valor_unitario: Optional[str] = None
    valor_total: Optional[str] = None
    codigo: Optional[str] = None
    page_num: int = 0
    confidence: float = 0.0
    raw_line: str = ""

@dataclass
class ExtractionResult:
    items: List[ExtractedItem] = field(default_factory=list)
    confidence_score: float = 0.0
    extraction_method: str = ""
    pages_used: List[int] = field(default_factory=list)
    needs_di: bool = True
    reason: str = ""

ITEM_PATTERNS = [
    re.compile(r'^\s*(?P<item>\d+(?:\.\d+)?)\s*[|\t]\s*(?P<desc>[^|\t]{10,}?)\s*[|\t]\s*(?P<un>\w{1,10})\s*[|\t]\s*(?P<qtd>[\d\.,]+)\s*[|\t]?\s*(?P<valor>[\d\.,]+)?', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*(?P<item>\d+(?:\.\d+)?)[.\-)\s]+\s*(?P<desc>[A-Za-z\u00C0-\u00FF][^|\n]{15,}?)(?:\s+(?P<qtd>\d+(?:[\.,]\d+)?)\s*(?P<un>un|pc|kg|m|l|cx|pct|und|unid))?', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*(?P<item>\d{1,4})\s{2,}(?P<desc>[A-Za-z\u00C0-\u00FF][^\n]{10,}?)\s{2,}(?P<un>\w{1,10})\s{2,}(?P<qtd>[\d\.,]+)\s{2,}(?P<vunit>[\d\.,]+)?\s*(?P<vtotal>[\d\.,]+)?', re.IGNORECASE | re.MULTILINE),
    re.compile(r'item\s*(?P<item>\d+(?:\.\d+)?)\s*[-:\s]\s*(?P<desc>[A-Za-z\u00C0-\u00FF][^;.\n]{10,})', re.IGNORECASE),
    re.compile(r'(?P<item>\d+(?:\.\d+)?)\s*[).\-]\s*(?P<desc>[A-Za-z\u00C0-\u00FF][^;]{10,}?)(?:quantidade|qtd|qtde)[:\s]*(?P<qtd>\d+(?:[\.,]\d+)?)\s*(?P<un>un|unid|unidade|kg|m|l|cx|caixa|pct|pacote)?s?', re.IGNORECASE),
    re.compile(r'^\s*(?P<item>\d{1,3})\s*[-.\)]\s*(?P<desc>[A-Za-z\u00C0-\u00FF][^\n]{8,80})$', re.IGNORECASE | re.MULTILINE),
]

def clean_description(desc):
    if not desc:
        return ""
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()

def clean_number(num):
    if not num:
        return ""
    return num.strip().replace(' ', '')

def extract_items_from_text(text, page_num=0):
    items = []
    used_lines = set()
    for pattern in ITEM_PATTERNS:
        for match in pattern.finditer(text):
            start = match.start()
            if any(abs(start - used) < 50 for used in used_lines):
                continue
            groups = match.groupdict()
            item_num = groups.get('item', '').strip()
            desc = clean_description(groups.get('desc', ''))
            if not item_num or not desc or len(desc) < 10:
                continue
            confidence = 0.5
            if groups.get('un'):
                confidence += 0.1
            if groups.get('qtd'):
                confidence += 0.15
            if groups.get('vunit') or groups.get('valor'):
                confidence += 0.15
            if groups.get('vtotal'):
                confidence += 0.1
            context_start = max(0, start - 75)
            context_end = min(len(text), match.end() + 75)
            raw_with_context = text[context_start:context_end].replace('\n', ' ').replace('\r', '')
            extracted = ExtractedItem(numero=item_num, descricao=desc, unidade=groups.get('un', ''),
                                       quantidade=clean_number(groups.get('qtd', '')),
                                       valor_unitario=clean_number(groups.get('vunit', '') or groups.get('valor', '')),
                                       valor_total=clean_number(groups.get('vtotal', '')),
                                       codigo=groups.get('codigo', ''), page_num=page_num,
                                       confidence=confidence, raw_line=raw_with_context)
            items.append(extracted)
            used_lines.add(start)
    return items

def calculate_extraction_confidence(items):
    if not items:
        return 0.0, "Nenhum item encontrado"
    scores = {
        'quantity': len(items) >= 3,
        'completeness': sum(1 for i in items if i.quantidade) / len(items) >= 0.7,
        'item_confidence': sum(i.confidence for i in items) / len(items) >= 0.6,
    }
    weights = {'quantity': 0.35, 'completeness': 0.35, 'item_confidence': 0.3}
    final_score = sum(weights[k] * (1.0 if v else 0.0) for k, v in scores.items())
    failed = [k for k, v in scores.items() if not v]
    reason = f"Criterios nao atendidos: {', '.join(failed)}" if failed else "Todos os criterios atendidos"
    return final_score, reason

def extract_items_raw(pages_text, candidate_pages=None):
    all_items = []
    pages_used = []
    pages_to_scan = candidate_pages if candidate_pages else list(pages_text.keys())
    for page_num in pages_to_scan:
        if page_num not in pages_text:
            continue
        text = pages_text[page_num]
        items = extract_items_from_text(text, page_num)
        if items:
            all_items.extend(items)
            pages_used.append(page_num)
    unique_items = {}
    for item in all_items:
        key = f"{item.numero}_{item.descricao[:30]}"
        if key not in unique_items or item.confidence > unique_items[key].confidence:
            unique_items[key] = item
    final_items = list(unique_items.values())
    final_items.sort(key=lambda x: (x.page_num, float(x.numero.replace('.', '')) if x.numero.replace('.', '').isdigit() else 0))
    confidence, reason = calculate_extraction_confidence(final_items)
    needs_di = confidence < 0.75
    return ExtractionResult(items=final_items, confidence_score=confidence, extraction_method="raw_regex",
                            pages_used=pages_used, needs_di=needs_di, reason=reason)

def to_dict(result):
    return {
        'total_items': len(result.items),
        'confidence_score': round(result.confidence_score, 3),
        'confidence_percent': f"{result.confidence_score * 100:.1f}%",
        'extraction_method': result.extraction_method,
        'pages_used': result.pages_used,
        'needs_di': result.needs_di,
        'recommendation': 'ENVIAR_PARA_DI' if result.needs_di else 'USAR_DIRETO',
        'reason': result.reason,
        'items': [{'item': i.numero, 'descricao': i.descricao, 'unidade': i.unidade, 'quantidade': i.quantidade,
                   'valor_unitario': i.valor_unitario, 'valor_total': i.valor_total, 'codigo': i.codigo,
                   'pagina': i.page_num, 'confidence': round(i.confidence, 2), 'raw_line': i.raw_line} for i in result.items]
    }
