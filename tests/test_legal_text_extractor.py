# tests/test_legal_text_extractor.py
"""
Testes para o extrator de texto unificado.
Testa logica de normalizacao e dispatch por extensao.
Nao testa PDF/DOCX real (requer arquivos binarios) — testa interface e validacao.
"""
from __future__ import annotations

import pytest

from govy.legal.text_extractor import extract, _normalize_text, _sha256


class TestNormalizeText:
    def test_replaces_nbsp(self):
        assert _normalize_text("hello\u00a0world") == "hello world"

    def test_collapses_spaces(self):
        assert _normalize_text("hello    world") == "hello world"

    def test_collapses_tabs(self):
        assert _normalize_text("hello\t\tworld") == "hello world"

    def test_normalizes_line_endings(self):
        assert _normalize_text("a\r\nb\rc") == "a\nb\nc"

    def test_collapses_newlines(self):
        result = _normalize_text("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_strips(self):
        assert _normalize_text("  hello  ") == "hello"

    def test_empty(self):
        assert _normalize_text("") == ""
        assert _normalize_text(None) == ""


class TestSha256:
    def test_deterministic(self):
        h1 = _sha256("hello world")
        h2 = _sha256("hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_different_inputs(self):
        h1 = _sha256("hello")
        h2 = _sha256("world")
        assert h1 != h2


class TestExtractDispatch:
    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Formato nao suportado"):
            extract(b"data", "file.txt")

    def test_pdf_extension_returns_empty_on_invalid(self):
        # Invalid PDF bytes → graceful empty result (no crash)
        result = extract(b"not a real pdf", "test.pdf")
        assert result.source_format == "pdf"
        assert result.char_count == 0

    def test_docx_extension_accepted(self):
        with pytest.raises(Exception):
            extract(b"not a real docx", "test.docx")

    def test_case_insensitive_extension(self):
        # Invalid PDF bytes → graceful empty result
        result = extract(b"data", "TEST.PDF")
        assert result.source_format == "pdf"
