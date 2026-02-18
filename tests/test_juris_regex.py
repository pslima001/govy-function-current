"""Tests for govy.utils.juris_regex - regex patterns and extraction."""

import sys
import os

# Ensure govy package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.utils.juris_regex import has_fundamento_legal, extract_legal_references


# ── has_fundamento_legal: positive cases ─────────────────────────────────────


def test_cf88():
    result, matches = has_fundamento_legal("Conforme CF/88, art. 37")
    assert result is True
    assert any("CF/88" in m for m in matches)


def test_crfb88():
    result, matches = has_fundamento_legal("nos termos da CRFB/88")
    assert result is True
    assert any("CRFB/88" in m for m in matches)


def test_constituicao_federal():
    result, matches = has_fundamento_legal("art. 37 da Constituição Federal")
    assert result is True
    assert any("Constituição Federal" in m for m in matches)


def test_art_37_a():
    result, matches = has_fundamento_legal("conforme art. 37-A da Lei 14.133/2021")
    assert result is True
    assert any("art. 37-A" in m for m in matches)


def test_paragrafo_ordinal():
    result, matches = has_fundamento_legal("§ 1º do art. 62")
    assert result is True
    assert any("§ 1º" in m for m in matches)


def test_paragrafo_grau():
    result, matches = has_fundamento_legal("§ 2° determina")
    assert result is True
    assert any("§ 2°" in m for m in matches)


def test_lei_14133_2021():
    result, matches = has_fundamento_legal("Lei 14.133/2021 dispoe sobre...")
    assert result is True
    assert any("14.133/2021" in m for m in matches)


def test_lei_com_de():
    result, matches = has_fundamento_legal("Lei 14.133 de 2021 regulamenta...")
    assert result is True
    assert any("14.133" in m for m in matches)


def test_sumula():
    result, matches = has_fundamento_legal("Súmula 247 do TCU")
    assert result is True
    assert any("Súmula 247" in m for m in matches)


def test_decreto():
    result, matches = has_fundamento_legal("Decreto 10.024/2019")
    assert result is True
    assert any("Decreto 10.024/2019" in m for m in matches)


def test_paragrafo_unico():
    result, matches = has_fundamento_legal("parágrafo único do art. 75")
    assert result is True
    assert any("parágrafo único" in m for m in matches)


# ── has_fundamento_legal: negative cases ─────────────────────────────────────


def test_generic_text_no_legal():
    result, matches = has_fundamento_legal("O licitante foi inabilitado por falta de documentos.")
    assert result is False
    assert matches == []


def test_empty_text():
    result, matches = has_fundamento_legal("")
    assert result is False
    assert matches == []


def test_none_text():
    result, matches = has_fundamento_legal(None)
    assert result is False
    assert matches == []


def test_no_legal_refs_generic():
    result, matches = has_fundamento_legal("A empresa não comprovou capacidade técnica.")
    assert result is False
    assert matches == []


# ── extract_legal_references: categories ─────────────────────────────────────


def test_extract_constituicao_category():
    refs = extract_legal_references("art. 37 da Constituição Federal e CF/88")
    assert refs["found"] is True
    assert "constituicao" in refs["references"]
    assert "artigos" in refs["references"]


def test_extract_artigo_with_suffix():
    refs = extract_legal_references("art. 37-A da Lei 14.133/2021")
    assert refs["found"] is True
    artigos = refs["references"].get("artigos", [])
    assert any("37-A" in a for a in artigos)


def test_extract_paragrafo_ordinal():
    refs = extract_legal_references("§ 1º do art. 62")
    assert refs["found"] is True
    paragrafos = refs["references"].get("paragrafos", [])
    assert any("§ 1º" in p for p in paragrafos)


def test_extract_empty():
    refs = extract_legal_references("")
    assert refs["found"] is False
    assert refs["references"] == {}


def test_extract_comprehensive():
    text = """
    Conforme art. 62, § 1º, inciso IV, alínea "a" da Lei 14.133/2021,
    combinado com o art. 37 da Constituição Federal e a Súmula 247 do TCU,
    bem como o Decreto 10.024/2019, é necessário observar o parágrafo único
    do artigo 75 da Lei nº 8.666/93.
    """
    refs = extract_legal_references(text)
    assert refs["found"] is True
    assert refs["total"] > 0
    assert "artigos" in refs["references"]
    assert "leis" in refs["references"]
    assert "sumulas" in refs["references"]
    assert "decretos" in refs["references"]
    assert "paragrafos" in refs["references"]
    assert "incisos" in refs["references"]
    assert "alineas" in refs["references"]
