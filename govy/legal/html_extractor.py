# govy/legal/html_extractor.py
"""
Extrator de texto a partir de HTML de legislacao (gov.br, Planalto).

Usa BeautifulSoup para remover nav/header/footer/scripts/styles e
extrair o bloco principal de conteudo normativo.

Reutiliza _normalize_text() e _sha256() de text_extractor.py.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from govy.legal.models import ExtractionResult
from govy.legal.text_extractor import _normalize_text, _sha256

logger = logging.getLogger(__name__)

# Tags a remover completamente (conteudo + tag)
_STRIP_TAGS = {"nav", "header", "footer", "script", "style", "noscript", "iframe"}

# Seletores CSS para tentar encontrar o bloco principal de conteudo
_CONTENT_SELECTORS = [
    "article",
    "div#content-core",
    'div[class*="content"]',
    "div#content",
    "main",
]


def _detect_encoding(html_bytes: bytes, encoding_hint: Optional[str] = None) -> str:
    """Detecta encoding do HTML."""
    if encoding_hint:
        return encoding_hint

    # Tenta meta charset no HTML
    head = html_bytes[:2048].decode("ascii", errors="ignore").lower()
    m = re.search(r'charset[="\s]+([a-zA-Z0-9\-_]+)', head)
    if m:
        return m.group(1).strip()

    return "utf-8"


def extract_html(html_bytes: bytes, encoding: Optional[str] = None) -> ExtractionResult:
    """
    Extrai texto limpo de HTML de legislacao.

    Args:
        html_bytes: conteudo HTML em bytes
        encoding: encoding explícito (se None, detecta automaticamente)

    Returns:
        ExtractionResult com texto normalizado
    """
    from bs4 import BeautifulSoup

    enc = _detect_encoding(html_bytes, encoding)
    try:
        html_str = html_bytes.decode(enc, errors="replace")
    except (LookupError, UnicodeDecodeError):
        html_str = html_bytes.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html_str, "html.parser")

    # Remove tags indesejadas
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Tenta encontrar bloco principal de conteudo
    content_block = None
    for selector in _CONTENT_SELECTORS:
        content_block = soup.select_one(selector)
        if content_block:
            break

    if not content_block:
        content_block = soup.body or soup

    text = content_block.get_text(separator="\n")
    text = _normalize_text(text)

    return ExtractionResult(
        text=text,
        source_format="html",
        extractor="beautifulsoup",
        char_count=len(text),
        sha256=_sha256(text) if text else "",
    )
