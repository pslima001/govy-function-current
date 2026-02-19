"""Tests for govy.doctrine.semantic — pure functions only (no OpenAI calls)."""

from __future__ import annotations

from govy.doctrine.semantic import (
    ARGUMENT_ROLE_V1,
    _coerce_argument_role,
    _default_scope_assertions,
    _looks_neutral,
    _sanitize_text,
)


class TestSanitizeText:
    def test_clean_text_unchanged(self):
        text, flags = _sanitize_text("Texto limpo sem problemas")
        assert text == "Texto limpo sem problemas"
        assert flags == []

    def test_removes_consenso_majority(self):
        text, flags = _sanitize_text("Visão majoritária da doutrina")
        assert "majoritária" not in text.lower()
        assert "CONSENSO_REMOVIDO" in flags

    def test_removes_consenso_pacifico(self):
        text, flags = _sanitize_text("Entendimento pacífico sobre")
        assert "pacífico" not in text.lower()
        assert "CONSENSO_REMOVIDO" in flags

    def test_removes_consenso_consolidado(self):
        text, flags = _sanitize_text("Posição consolidado na doutrina")
        assert "consolidado" not in text.lower()
        assert "CONSENSO_REMOVIDO" in flags

    def test_removes_tribunal_tcu(self):
        text, flags = _sanitize_text("Conforme decidido pelo TCU")
        assert "tcu" not in text.lower()
        assert "MENCAO_TRIBUNAL_REMOVIDA" in flags

    def test_removes_tribunal_stj(self):
        text, flags = _sanitize_text("Segundo o STJ entende")
        assert "stj" not in text.lower()
        assert "MENCAO_TRIBUNAL_REMOVIDA" in flags

    def test_removes_authorship(self):
        text, flags = _sanitize_text("O autor sustenta que")
        assert "autor" not in text.lower()
        assert "AUTORIA_REMOVIDA" in flags

    def test_multiple_flags(self):
        text, flags = _sanitize_text("O autor e o TCU decidiram que é pacífico")
        assert "AUTORIA_REMOVIDA" in flags
        assert "MENCAO_TRIBUNAL_REMOVIDA" in flags
        assert "CONSENSO_REMOVIDO" in flags

    def test_empty_string(self):
        text, flags = _sanitize_text("")
        assert text == ""
        assert flags == []

    def test_collapses_whitespace(self):
        text, _ = _sanitize_text("word1   word2     word3")
        assert "  " not in text

    def test_flags_are_sorted_and_deduplicated(self):
        text, flags = _sanitize_text("TCU e STJ decidem")
        assert flags == sorted(set(flags))


class TestLooksNeutral:
    def test_neutral_ha_visoes(self):
        assert _looks_neutral("Há visões doutrinárias que sustentam...") is True

    def test_neutral_parte_da_doutrina(self):
        assert _looks_neutral("Parte da doutrina entende que...") is True

    def test_neutral_alguns_advogados(self):
        assert _looks_neutral("Alguns advogados descrevem a situação...") is True

    def test_not_neutral(self):
        assert _looks_neutral("A lei determina que...") is False

    def test_empty(self):
        assert _looks_neutral("") is False

    def test_case_insensitive_via_lower(self):
        assert _looks_neutral("HÁ VISÕES DOUTRINÁRIAS que...") is True

    def test_whitespace_trimmed(self):
        assert _looks_neutral("  Há visões doutrinárias que...  ") is True


class TestCoerceArgumentRole:
    def test_valid_role(self):
        assert _coerce_argument_role("DEFINICAO") == "DEFINICAO"

    def test_valid_role_lowercase(self):
        assert _coerce_argument_role("definicao") == "DEFINICAO"

    def test_valid_role_with_whitespace(self):
        assert _coerce_argument_role("  LIMITE  ") == "LIMITE"

    def test_invalid_role_returns_none(self):
        assert _coerce_argument_role("INVALID_ROLE") is None

    def test_none_returns_none(self):
        assert _coerce_argument_role(None) is None

    def test_all_v1_roles_accepted(self):
        for role in ARGUMENT_ROLE_V1:
            assert _coerce_argument_role(role) == role


class TestDefaultScopeAssertions:
    def test_returns_all_false(self):
        scope = _default_scope_assertions()
        assert all(v is False for v in scope.values())

    def test_has_expected_keys(self):
        scope = _default_scope_assertions()
        expected = {"decide_caso_concreto", "substitui_jurisprudencia", "afirma_consenso", "revela_autoria"}
        assert set(scope.keys()) == expected
