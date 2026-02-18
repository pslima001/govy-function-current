"""Tests for govy.doctrine.verbatim_classifier — verbatim legal text detection."""

from __future__ import annotations

from govy.doctrine.verbatim_classifier import is_verbatim_legal_text


class TestIsVerbatimLegalText:
    def test_empty_string(self):
        assert is_verbatim_legal_text("") is False

    def test_none_like(self):
        assert is_verbatim_legal_text("") is False

    def test_short_text_rejected(self):
        assert is_verbatim_legal_text("TCU STJ") is False  # < 50 chars

    def test_strong_pattern_acordao(self):
        text = "Conforme o Acórdão no 1234/2023, o Tribunal decidiu que " + "x" * 50
        assert is_verbatim_legal_text(text) is True

    def test_strong_pattern_ementa(self):
        text = "EMENTA: A licitação deve observar os princípios " + "x" * 50
        assert is_verbatim_legal_text(text) is True

    def test_strong_pattern_relator(self):
        text = "Relator: Ministro Fulano de Tal, processo de licitação " + "x" * 50
        assert is_verbatim_legal_text(text) is True

    def test_strong_pattern_plenario(self):
        text = "O Plenário decidiu por unanimidade que a contratação " + "x" * 50
        assert is_verbatim_legal_text(text) is True

    def test_medium_patterns_single_not_enough(self):
        text = "O TCU publicou orientações sobre contratações públicas " + "x" * 50
        assert is_verbatim_legal_text(text) is False  # only 1 medium match

    def test_medium_patterns_two_matches(self):
        text = "O TCU e o STJ decidiram conjuntamente sobre a matéria " + "x" * 50
        assert is_verbatim_legal_text(text) is True  # 2 medium matches

    def test_doctrine_text_not_verbatim(self):
        text = (
            "A doutrina entende que o princípio da legalidade na licitação "
            "impõe ao administrador público o dever de observar estritamente "
            "os requisitos previstos na legislação vigente."
        )
        assert is_verbatim_legal_text(text) is False

    def test_case_insensitive(self):
        text = "acórdão no 9999 do tribunal de contas da união sobre " + "x" * 50
        assert is_verbatim_legal_text(text) is True
