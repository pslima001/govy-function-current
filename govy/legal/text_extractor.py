# govy/legal/text_extractor.py
"""
Extrator de texto unificado para documentos legais (PDF e DOCX).

Reutiliza:
  - tce_parser_v3.extract_text_pymupdf / extract_text_pdfplumber (PDF)
  - doctrine/reader_docx.read_docx_bytes (DOCX)
  - tce_parser_v3.normalize_text

Retorna ExtractionResult com texto limpo, formato, extrator, contagem, hash.
"""
from __future__ import annotations

import hashlib
import logging

from govy.legal.models import ExtractionResult

logger = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_text(text: str) -> str:
    """Normalizacao inline (mesma logica de tce_parser_v3.normalize_text)."""
    import re
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Extrai texto de PDF usando PyMuPDF com fallback para pdfplumber."""
    import fitz
    text = ""
    extractor = "pymupdf"

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = []
        for i in range(len(doc)):
            parts.append(doc[i].get_text("text") or "")
        text = _normalize_text("\n".join(parts))
    except Exception as e:
        logger.warning("PyMuPDF falhou: %s", e)
        text = ""

    if not text or len(text) < 200:
        try:
            import pdfplumber
            import io
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                parts = []
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            text = _normalize_text("\n".join(parts))
            extractor = "pdfplumber"
        except Exception as e:
            logger.error("pdfplumber tambem falhou: %s", e)
            text = ""

    text = _normalize_text(text)
    return ExtractionResult(
        text=text,
        source_format="pdf",
        extractor=extractor,
        char_count=len(text),
        sha256=_sha256(text) if text else "",
    )


def extract_docx(docx_bytes: bytes) -> ExtractionResult:
    """Extrai texto de DOCX usando python-docx."""
    from docx import Document
    from io import BytesIO

    if not docx_bytes:
        raise ValueError("docx_bytes vazio")

    doc = Document(BytesIO(docx_bytes))
    paras = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            t = " ".join(t.split())
            paras.append(t)

    text = _normalize_text("\n".join(paras))
    return ExtractionResult(
        text=text,
        source_format="docx",
        extractor="python-docx",
        char_count=len(text),
        sha256=_sha256(text) if text else "",
    )


def extract(file_bytes: bytes, filename: str) -> ExtractionResult:
    """
    Extrai texto de arquivo com base na extensao.

    Args:
        file_bytes: conteudo do arquivo
        filename: nome do arquivo (para detectar extensao)

    Returns:
        ExtractionResult
    """
    lower = filename.lower()
    if lower.endswith(".html") or lower.endswith(".htm"):
        from govy.legal.html_extractor import extract_html
        return extract_html(file_bytes)
    if lower.endswith(".docx"):
        return extract_docx(file_bytes)
    if lower.endswith(".pdf"):
        return extract_pdf(file_bytes)
    raise ValueError(f"Formato nao suportado: {filename} (esperado .pdf, .docx ou .html)")
