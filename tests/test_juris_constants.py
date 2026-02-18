"""Tests for govy.utils.juris_constants - clamp functions and enums."""

import sys
import os

# Ensure govy package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.utils.juris_constants import (
    VALID_EFFECT,
    clamp_effect,
    clamp_remedy_type,
    clamp_procedural_stage,
    clamp_holding_outcome,
)


# ── VALID_EFFECT includes NAO_CLARO ──────────────────────────────────────────


def test_valid_effect_contains_nao_claro():
    assert "NAO_CLARO" in VALID_EFFECT


def test_valid_effect_contains_all_values():
    expected = {"FLEXIBILIZA", "RIGORIZA", "CONDICIONAL", "NAO_CLARO"}
    assert VALID_EFFECT == expected


# ── clamp_effect fallback is NAO_CLARO ───────────────────────────────────────


def test_clamp_effect_valid_values():
    assert clamp_effect("FLEXIBILIZA") == "FLEXIBILIZA"
    assert clamp_effect("RIGORIZA") == "RIGORIZA"
    assert clamp_effect("CONDICIONAL") == "CONDICIONAL"
    assert clamp_effect("NAO_CLARO") == "NAO_CLARO"


def test_clamp_effect_fallback_nao_claro():
    """Unknown values must fall back to NAO_CLARO, not CONDICIONAL."""
    assert clamp_effect("VALOR_INVENTADO") == "NAO_CLARO"
    assert clamp_effect("") == "NAO_CLARO"
    assert clamp_effect(None) == "NAO_CLARO"


def test_clamp_effect_mappings():
    assert clamp_effect("FLEXIBILIZACAO") == "FLEXIBILIZA"
    assert clamp_effect("VEDOU") == "RIGORIZA"
    assert clamp_effect("DESDE_QUE") == "CONDICIONAL"
    assert clamp_effect("NAO_APLICAVEL") == "NAO_CLARO"


# ── clamp_remedy_type fallback is NAO_CLARO ──────────────────────────────────


def test_clamp_remedy_type_valid_values():
    assert clamp_remedy_type("IMPUGNACAO") == "IMPUGNACAO"
    assert clamp_remedy_type("RECURSO") == "RECURSO"
    assert clamp_remedy_type("ORIENTACAO_GERAL") == "ORIENTACAO_GERAL"
    assert clamp_remedy_type("NAO_CLARO") == "NAO_CLARO"


def test_clamp_remedy_type_fallback_nao_claro():
    """Unknown values must fall back to NAO_CLARO, not ORIENTACAO_GERAL."""
    assert clamp_remedy_type("VALOR_INVENTADO") == "NAO_CLARO"
    assert clamp_remedy_type("") == "NAO_CLARO"
    assert clamp_remedy_type(None) == "NAO_CLARO"


def test_clamp_remedy_type_mappings():
    assert clamp_remedy_type("PEDIDO_REEXAME") == "RECURSO"
    assert clamp_remedy_type("CONSULTA") == "ORIENTACAO_GERAL"
    assert clamp_remedy_type("NAO_APLICAVEL") == "NAO_CLARO"


# ── Other clamp functions still work ─────────────────────────────────────────


def test_clamp_procedural_stage_basic():
    assert clamp_procedural_stage("EDITAL") == "EDITAL"
    assert clamp_procedural_stage("LICITACAO") == "EDITAL"
    assert clamp_procedural_stage("INVENTADO") == "NAO_CLARO"
    assert clamp_procedural_stage("") == "NAO_CLARO"


def test_clamp_holding_outcome_basic():
    assert clamp_holding_outcome("MANTEVE") == "MANTEVE"
    assert clamp_holding_outcome("ACOLHEU") == "AFASTOU"
    assert clamp_holding_outcome("INVENTADO") == "NAO_CLARO"
    assert clamp_holding_outcome("") == "NAO_CLARO"
