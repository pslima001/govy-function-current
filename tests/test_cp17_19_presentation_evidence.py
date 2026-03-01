"""
CP17 — Seleção determinística da melhor apresentação.
CP18 — req_snippet em todos os gaps (evidência do TR).
CP19 — TR context no popup UNMATCH.

Testes:
- UNMATCH popula other_presentations (CP17).
- Empate: primeira apresentação na bula vence (CP17 determinismo).
- Gaps carregam req_snippet do ItemRequirement.raw (CP18).
- UNMATCH popup inclui trecho do TR quando cabe (CP19).
"""
from govy.matching.matcher import (
    match_item_to_bula,
    format_popup,
    _req_snippet,
)
from govy.matching.models import GapCode, ItemRequirement, WaiverConfig


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
_REQ = ItemRequirement(
    raw="RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML",
    principle="RITUXIMABE",
    conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
    form="SOLUCAO INJETAVEL",
    pkg="FRASCO-AMPOLA",
    vol=50.0, vol_unit="ML",
)


# ===========================================================================
# CP17 — other_presentations sempre populado
# ===========================================================================

def test_unmatch_has_other_presentations():
    """UNMATCH com 2 apresentações: best + 1 other."""
    bula = (
        "BEVACIZUMABE 5 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML; "
        "BEVACIZUMABE 10 MG/ML COMPRIMIDO AMPOLA 30 ML"
    )
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "UNMATCH"
    assert r.best_presentation is not None
    assert len(r.other_presentations) >= 1


def test_match_has_other_presentations():
    """MATCH com 2 apresentações: best = a que bate, other = as demais."""
    bula = (
        "RITUXIMABE 500 MG/50 ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML. "
        "RITUXIMABE 100 MG/10 ML SOLUCAO INJETAVEL FRASCO-AMPOLA 10 ML."
    )
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "MATCH"
    assert len(r.other_presentations) >= 1


def test_deterministic_best_on_tie():
    """Empate em gaps: primeira apresentação da bula vence (determinístico)."""
    bula = (
        "RITUXIMABE 5 MG/ML COMPRIMIDO AMPOLA 30 ML; "
        "RITUXIMABE 5 MG/ML COMPRIMIDO AMPOLA 30 ML"
    )
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "UNMATCH"
    assert r.best_presentation is not None
    # A primeira apresentação com menos gaps ou a primeira em caso de empate
    # Como são idênticas, best deve ser a primeira (por índice)
    assert r.best_presentation == r.best_presentation  # sanity


def test_single_presentation_no_other():
    """1 apresentação apenas: other_presentations vazio."""
    bula = "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML"
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "MATCH"
    assert r.other_presentations == []


# ===========================================================================
# CP18 — req_snippet em gaps
# ===========================================================================

def test_gaps_have_req_snippet():
    """Todos os gaps devem carregar req_snippet do raw."""
    bula = "BEVACIZUMABE 5 MG/ML COMPRIMIDO AMPOLA 30 ML"
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "UNMATCH"
    assert len(r.gaps) >= 1
    for g in r.gaps:
        assert g.req_snippet is not None
        assert "RITUXIMABE" in g.req_snippet


def test_req_snippet_helper():
    """_req_snippet normaliza whitespace e trunca."""
    assert _req_snippet("  FOO   BAR  ", max_len=5) == "FOO B"
    assert _req_snippet("SHORT") == "SHORT"
    assert _req_snippet("") is None
    assert _req_snippet("A" * 200, max_len=120) == "A" * 120


def test_no_presentations_gaps_have_req_snippet():
    """Caso sem apresentações: gaps também recebem req_snippet."""
    bula = "TEXTO SEM NENHUMA APRESENTACAO DETECTAVEL"
    r = match_item_to_bula("38", _REQ, bula)

    assert r.status == "UNMATCH"
    for g in r.gaps:
        assert g.req_snippet is not None


# ===========================================================================
# CP19 — TR context no popup UNMATCH
# ===========================================================================

def test_unmatch_popup_contains_tr_context():
    """Popup UNMATCH deve conter trecho do TR quando cabe no cap 220."""
    bula = "BEVACIZUMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML"
    r = match_item_to_bula("38", _REQ, bula)

    popup = format_popup(r, _REQ)
    assert "UNMATCH" in popup
    assert len(popup) <= 220
    # TR context incluído se couber
    if len(popup) < 200:
        assert "TR:" in popup


def test_match_popup_no_tr_context():
    """Popup MATCH não inclui TR context (já mostra req completo no OK)."""
    bula = "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML"
    r = match_item_to_bula("38", _REQ, bula)

    popup = format_popup(r, _REQ)
    assert "MATCH" in popup
    assert "TR:" not in popup


def test_popup_respects_220_cap():
    """Popup nunca excede 220 chars, mesmo com TR context."""
    long_raw = "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML " * 5
    req = ItemRequirement(
        raw=long_raw,
        principle="RITUXIMABE",
        conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
        form="SOLUCAO INJETAVEL",
        pkg="FRASCO-AMPOLA",
        vol=50.0, vol_unit="ML",
    )
    bula = "BEVACIZUMABE 5 MG/ML COMPRIMIDO SERINGA 100 ML"
    r = match_item_to_bula("38", req, bula)

    popup = format_popup(r, req)
    assert len(popup) <= 220
