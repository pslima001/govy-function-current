"""
Govy - Base para Extractors Regex-Only
=======================================

Parâmetros que podem ser extraídos exclusivamente via regex,
sem necessidade de validação por LLM (custo zero).

Estrutura de resposta padrão:
{
    "encontrado": bool,
    "valor": str,           # Valor extraído (ex: "60 dias", "SIM", "ITEM")
    "confianca": str,       # "alta", "media", "baixa"
    "evidencia": str,       # Trecho do texto onde foi encontrado
    "detalhes": dict        # Informações adicionais específicas do parâmetro
}

Se confiança == "baixa", o frontend pode optar por chamar LLMs para validação.
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class RegexResult:
    """Resultado padronizado de extração regex-only"""
    encontrado: bool = False
    valor: str = ""
    confianca: str = "baixa"  # alta, media, baixa
    evidencia: str = ""
    detalhes: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


def extract_context(texto: str, match: re.Match, chars_antes: int = 100, chars_depois: int = 150) -> str:
    """Extrai contexto ao redor do match para evidência"""
    start = max(0, match.start() - chars_antes)
    end = min(len(texto), match.end() + chars_depois)
    context = texto[start:end].strip()
    # Limpa quebras de linha excessivas
    context = re.sub(r'\s+', ' ', context)
    return context


def normalize_text(texto: str) -> str:
    """Normaliza texto para busca (lowercase, sem acentos extras de espaço)"""
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def fix_encoding(texto: str) -> str:
    """
    Corrige problemas comuns de encoding (UTF-8 lido como Latin-1).
    
    Exemplos:
    - "Ã§" -> "ç"
    - "Ã£" -> "ã"  
    - "Ã¡" -> "á"
    """
    # Tenta primeiro o método mais robusto: re-encode
    try:
        # Se o texto foi lido como Latin-1 mas era UTF-8
        texto = texto.encode('latin-1').decode('utf-8')
        return texto
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    
    # Fallback: substituições manuais dos casos mais comuns
    replacements = [
        ('Ã§', 'ç'), ('Ã‡', 'Ç'),
        ('Ã£', 'ã'), ('Ãƒ', 'Ã'),
        ('Ã¡', 'á'),
        ('Ã©', 'é'), ('Ã‰', 'É'),
        ('Ãª', 'ê'), ('ÃŠ', 'Ê'),
        ('Ã­', 'í'),
        ('Ã³', 'ó'), ('Ã"', 'Ó'),
        ('Ãµ', 'õ'), ('Ã•', 'Õ'),
        ('Ã´', 'ô'),
        ('Ãº', 'ú'), ('Ãš', 'Ú'),
        ('Ã¢', 'â'), ('Ã‚', 'Â'),
        ('Ã¼', 'ü'), ('Ãœ', 'Ü'),
        ('Ã±', 'ñ'),
        ('Â°', '°'), ('Âº', 'º'), ('Âª', 'ª'),
    ]
    
    for broken, fixed in replacements:
        texto = texto.replace(broken, fixed)
    
    return texto


def extract_number(texto: str) -> Optional[int]:
    """Extrai número de texto como '60 (sessenta)', '30', 'trinta'"""
    # Primeiro tenta número direto
    match = re.search(r'\d+', texto)
    if match:
        return int(match.group())
    
    # Mapeamento de números por extenso
    numeros_extenso = {
        'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'três': 3, 'tres': 3,
        'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8,
        'nove': 9, 'dez': 10, 'onze': 11, 'doze': 12, 'treze': 13,
        'quatorze': 14, 'catorze': 14, 'quinze': 15, 'dezesseis': 16,
        'dezessete': 17, 'dezoito': 18, 'dezenove': 19, 'vinte': 20,
        'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60,
        'setenta': 70, 'oitenta': 80, 'noventa': 90, 'cem': 100,
        'cento': 100, 'duzentos': 200, 'trezentos': 300
    }
    
    texto_lower = texto.lower()
    for palavra, valor in numeros_extenso.items():
        if palavra in texto_lower:
            return valor
    
    return None


def is_negative_context(texto: str, termos_negativos: List[str]) -> bool:
    """Verifica se o contexto contém termos negativos (sumário, índice, etc)"""
    texto_lower = texto.lower()
    for termo in termos_negativos:
        if termo.lower() in texto_lower:
            return True
    return False


# Termos negativos comuns (sumário, índice, etc)
TERMOS_NEGATIVOS_COMUNS = [
    'sumário', 'índice', 'indice', 'conteúdo', 'conteudo',
    'pág.', 'pag.', 'fl.', 'fls.',
    '......', '________', '--------', '======',  # Precisa de mais caracteres para ser considerado sumário
]
