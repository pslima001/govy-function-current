"""
Raw Item Extractor - Extrai itens diretamente do texto bruto (sem DI)
Camada 1 - Custo: ZERO
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ExtractedItem:
    """Item extraído do texto"""
    numero: str
    descricao: str
    unidade: Optional[str] = None
    quantidade: Optional[str] = None
    valor_unitario: Optional[str] = None
    valor_total: Optional[str] = None
    codigo: Optional[str] = None  # CATMAT/CATSER
    page_num: int = 0
    confidence: float = 0.0
    raw_line: str = ""


@dataclass 
class ExtractionResult:
    """Resultado da extração"""
    items: List[ExtractedItem] = field(default_factory=list)
    confidence_score: float = 0.0
    extraction_method: str = ""
    pages_used: List[int] = field(default_factory=list)
    needs_di: bool = True
    reason: str = ""


# Padrões para extração de itens
ITEM_PATTERNS = [
    # Padrão 1: ITEM | DESCRIÇÃO | UN | QTD | VALOR
    # Ex: "1 | Caneta azul | UN | 100 | 1,50"
    re.compile(
        r'^\s*(?P<item>\d+(?:\.\d+)?)\s*[|\t]\s*'
        r'(?P<desc>[^|\t]{10,}?)\s*[|\t]\s*'
        r'(?P<un>\w{1,10})\s*[|\t]\s*'
        r'(?P<qtd>[\d\.,]+)\s*[|\t]?\s*'
        r'(?P<valor>[\d\.,]+)?',
        re.IGNORECASE | re.MULTILINE
    ),
    
    # Padrão 2: Linhas com número de item no início
    # Ex: "1. Caneta esferográfica azul, caixa com 50 unidades"
    re.compile(
        r'^\s*(?P<item>\d+(?:\.\d+)?)[.\-)\s]+\s*'
        r'(?P<desc>[A-Za-zÀ-ú][^|\n]{15,}?)'
        r'(?:\s+(?P<qtd>\d+(?:[\.,]\d+)?)\s*(?P<un>un|pç|pc|kg|m|l|cx|pct|und|unid))?',
        re.IGNORECASE | re.MULTILINE
    ),
    
    # Padrão 3: Tabela com espaços fixos
    # Ex: "001    Papel A4 500 folhas    RESMA    10    25,00    250,00"
    re.compile(
        r'^\s*(?P<item>\d{1,4})\s{2,}'
        r'(?P<desc>[A-Za-zÀ-ú][^\n]{10,}?)\s{2,}'
        r'(?P<un>\w{1,10})\s{2,}'
        r'(?P<qtd>[\d\.,]+)\s{2,}'
        r'(?P<vunit>[\d\.,]+)?\s*'
        r'(?P<vtotal>[\d\.,]+)?',
        re.IGNORECASE | re.MULTILINE
    ),
    
    # Padrão 4: Formato CATMAT/CATSER
    # Ex: "1 | 234567 | Caneta azul | UN | 100"
    re.compile(
        r'^\s*(?P<item>\d+)\s*[|\t]\s*'
        r'(?P<codigo>\d{5,8})\s*[|\t]\s*'
        r'(?P<desc>[^|\t]{10,}?)\s*[|\t]\s*'
        r'(?P<un>\w{1,10})\s*[|\t]\s*'
        r'(?P<qtd>[\d\.,]+)',
        re.IGNORECASE | re.MULTILINE
    ),
    
    # Padrão 5: Lote/Item combinado
    # Ex: "LOTE 1 - ITEM 1.1 - Descrição do produto"
    re.compile(
        r'(?:lote\s*(?P<lote>\d+)\s*[-–]\s*)?'
        r'item\s*(?P<item>\d+(?:\.\d+)?)\s*[-–:]\s*'
        r'(?P<desc>[A-Za-zÀ-ú][^\n]{15,})',
        re.IGNORECASE | re.MULTILINE
    ),
]

# Padrões para limpar descrição
CLEANUP_PATTERNS = [
    (r'\s+', ' '),  # Múltiplos espaços
    (r'^\s+|\s+$', ''),  # Trim
    (r'[|\t]+$', ''),  # Delimitadores no final
]


def clean_description(desc: str) -> str:
    """Limpa a descrição extraída"""
    if not desc:
        return ""
    for pattern, replacement in CLEANUP_PATTERNS:
        desc = re.sub(pattern, replacement, desc)
    return desc.strip()


def clean_number(num: str) -> str:
    """Limpa número (quantidade, valor)"""
    if not num:
        return ""
    return num.strip().replace(' ', '')


def extract_items_from_text(text: str, page_num: int = 0) -> List[ExtractedItem]:
    """
    Tenta extrair itens do texto usando múltiplos padrões.
    """
    items = []
    used_lines = set()
    
    for pattern in ITEM_PATTERNS:
        for match in pattern.finditer(text):
            # Evitar duplicatas
            start = match.start()
            if any(abs(start - used) < 50 for used in used_lines):
                continue
            
            groups = match.groupdict()
            
            # Validar que temos pelo menos item e descrição
            item_num = groups.get('item', '').strip()
            desc = clean_description(groups.get('desc', ''))
            
            if not item_num or not desc or len(desc) < 10:
                continue
            
            # Calcular confiança baseado em campos preenchidos
            confidence = 0.5  # Base
            if groups.get('un'):
                confidence += 0.1
            if groups.get('qtd'):
                confidence += 0.15
            if groups.get('vunit') or groups.get('valor_unitario'):
                confidence += 0.15
            if groups.get('vtotal') or groups.get('valor_total'):
                confidence += 0.1
            if groups.get('codigo'):
                confidence += 0.1
            
            extracted = ExtractedItem(
                numero=item_num,
                descricao=desc,
                unidade=groups.get('un', ''),
                quantidade=clean_number(groups.get('qtd', '')),
                valor_unitario=clean_number(groups.get('vunit', '') or groups.get('valor_unitario', '')),
                valor_total=clean_number(groups.get('vtotal', '') or groups.get('valor_total', '')),
                codigo=groups.get('codigo', ''),
                page_num=page_num,
                confidence=confidence,
                raw_line=match.group(0)[:200]
            )
            
            items.append(extracted)
            used_lines.add(start)
    
    return items


def calculate_extraction_confidence(items: List[ExtractedItem]) -> Tuple[float, str]:
    """
    Calcula confiança geral da extração e determina se precisa DI.
    
    Returns:
        (confidence_score, reason)
    """
    if not items:
        return 0.0, "Nenhum item encontrado"
    
    # Critérios de confiança
    scores = {
        'quantity': len(items) >= 3,  # Pelo menos 3 itens
        'completeness': sum(1 for i in items if i.quantidade) / len(items) >= 0.7,  # 70% com quantidade
        'item_confidence': sum(i.confidence for i in items) / len(items) >= 0.6,  # Média de confiança
        'sequential': _check_sequential_items(items),  # Itens em sequência
    }
    
    # Calcular score final
    weights = {'quantity': 0.25, 'completeness': 0.3, 'item_confidence': 0.25, 'sequential': 0.2}
    final_score = sum(weights[k] * (1.0 if v else 0.0) for k, v in scores.items())
    
    # Razão
    failed = [k for k, v in scores.items() if not v]
    if failed:
        reason = f"Critérios não atendidos: {', '.join(failed)}"
    else:
        reason = "Todos os critérios atendidos"
    
    return final_score, reason


def _check_sequential_items(items: List[ExtractedItem]) -> bool:
    """Verifica se os itens estão em sequência numérica"""
    if len(items) < 2:
        return True
    
    try:
        # Extrair apenas parte inteira do número do item
        numbers = []
        for item in items:
            num_str = item.numero.split('.')[0]
            numbers.append(int(num_str))
        
        # Verificar se há sequência (permite gaps de até 2)
        numbers.sort()
        gaps = sum(1 for i in range(1, len(numbers)) if numbers[i] - numbers[i-1] > 2)
        return gaps <= len(numbers) * 0.2  # Máximo 20% de gaps
    except:
        return False


def extract_items_raw(pages_text: Dict[int, str], candidate_pages: List[int] = None) -> ExtractionResult:
    """
    Extrai itens de múltiplas páginas de texto.
    
    Args:
        pages_text: Dict {page_num: text}
        candidate_pages: Lista de páginas candidatas (se None, usa todas)
        
    Returns:
        ExtractionResult com itens e score de confiança
    """
    all_items = []
    pages_used = []
    
    # Usar apenas páginas candidatas se especificado
    pages_to_scan = candidate_pages if candidate_pages else list(pages_text.keys())
    
    for page_num in pages_to_scan:
        if page_num not in pages_text:
            continue
        
        text = pages_text[page_num]
        items = extract_items_from_text(text, page_num)
        
        if items:
            all_items.extend(items)
            pages_used.append(page_num)
    
    # Remover duplicatas (mesmo número de item)
    unique_items = {}
    for item in all_items:
        key = f"{item.numero}_{item.descricao[:30]}"
        if key not in unique_items or item.confidence > unique_items[key].confidence:
            unique_items[key] = item
    
    final_items = list(unique_items.values())
    final_items.sort(key=lambda x: (x.page_num, float(x.numero.replace('.', '')) if x.numero.replace('.', '').isdigit() else 0))
    
    # Calcular confiança
    confidence, reason = calculate_extraction_confidence(final_items)
    
    # Determinar se precisa DI
    needs_di = confidence < 0.75  # Threshold de 75%
    
    return ExtractionResult(
        items=final_items,
        confidence_score=confidence,
        extraction_method="raw_regex",
        pages_used=pages_used,
        needs_di=needs_di,
        reason=reason
    )


def to_dict(result: ExtractionResult) -> Dict:
    """Converte resultado para dict (JSON-serializable)"""
    return {
        'total_items': len(result.items),
        'confidence_score': round(result.confidence_score, 3),
        'confidence_percent': f"{result.confidence_score * 100:.1f}%",
        'extraction_method': result.extraction_method,
        'pages_used': result.pages_used,
        'needs_di': result.needs_di,
        'recommendation': 'ENVIAR_PARA_DI' if result.needs_di else 'USAR_DIRETO',
        'reason': result.reason,
        'items': [
            {
                'item': i.numero,
                'descricao': i.descricao,
                'unidade': i.unidade,
                'quantidade': i.quantidade,
                'valor_unitario': i.valor_unitario,
                'valor_total': i.valor_total,
                'codigo': i.codigo,
                'pagina': i.page_num,
                'confidence': round(i.confidence, 2)
            }
            for i in result.items
        ]
    }


if __name__ == "__main__":
    # Teste com texto de exemplo
    test_text = """
    TERMO DE REFERÊNCIA
    
    1 | Caneta esferográfica azul | UN | 100 | 1,50 | 150,00
    2 | Papel A4 500 folhas | RESMA | 50 | 25,00 | 1.250,00
    3 | Grampeador de mesa | UN | 10 | 35,00 | 350,00
    4 | Clips niquelado 2/0 | CX | 20 | 5,00 | 100,00
    5 | Borracha branca | UN | 50 | 0,80 | 40,00
    """
    
    items = extract_items_from_text(test_text, page_num=1)
    print(f"Itens encontrados: {len(items)}")
    for item in items:
        print(f"  {item.numero}: {item.descricao[:50]}... (conf: {item.confidence})")
