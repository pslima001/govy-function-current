import fitz
import os

# Testar com um PDF local se tiver, ou baixar
# Por enquanto vamos testar os indicadores

test_text = '''
TERMO DE REFERÊNCIA

ITEM | DESCRIÇÃO | UNIDADE | QTD | VALOR UNITÁRIO | VALOR TOTAL
1 | Caneta azul | UN | 100 | 1,50 | 150,00
2 | Papel A4 | RESMA | 50 | 25,00 | 1250,00
'''

# Importar o scanner
import sys
sys.path.insert(0, '.')
from govy_items_raw.pdf_scanner import scan_page

result = scan_page(1, test_text)
print(f'Score: {result.score}')
print(f'Is candidate: {result.is_candidate}')
print(f'Indicators: {result.indicators_found}')
