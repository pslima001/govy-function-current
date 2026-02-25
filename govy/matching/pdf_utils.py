"""
govy.matching.pdf_utils — Utilitário opcional para extração de texto de PDFs.

Usado para converter bulas/fichas em PDF para texto antes do matching.
Tenta PyMuPDF primeiro, depois pdfplumber como fallback.

Nota: se o texto já vem de outro pipeline (ex: Azure Document Intelligence),
este módulo não é necessário.
"""
from __future__ import annotations


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrai texto de PDF de bula (sem OCR).

    Estratégia:
    1. PyMuPDF (fitz) — mais rápido, melhor para PDFs simples
    2. pdfplumber — fallback, melhor para PDFs com tabelas

    Args:
        pdf_path: Caminho para o arquivo PDF.

    Returns:
        Texto extraído concatenado. String vazia se falhar.
    """
    # PyMuPDF
    try:
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open(pdf_path)
        parts = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        doc.close()
        txt = "\n".join(parts)
        if txt.strip():
            return txt
    except Exception:
        pass

    # pdfplumber fallback
    try:
        import pdfplumber  # type: ignore[import-untyped]

        parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""
