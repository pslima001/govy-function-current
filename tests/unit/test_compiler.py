"""Tests for the ruleset compiler (tabs-based structure)."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from govy.classification.compiler import (
    CompiledClass,
    CompiledProcedure,
    CompiledRuleset,
    RulesetCompilationError,
    load_ruleset,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def test_rules_dir(tmp_path: Path) -> Path:
    """Create a temporary rules directory with test fixtures."""
    rules = tmp_path / "rules"
    rules.mkdir()
    tribunals = rules / "tribunals"
    tribunals.mkdir()

    shutil.copy(FIXTURES / "core_test.json", rules / "core.json")
    shutil.copy(FIXTURES / "overlay_test.json", tribunals / "test-tribunal.json")
    return rules


# --- Test: load core only ---------------------------------------------------


def test_load_core_only(test_rules_dir: Path) -> None:
    """Loading with tribunal_id='core' should use only core rules."""
    rs = load_ruleset("core", rules_dir=test_rules_dir)

    assert rs.tribunal_id == "core"
    assert rs.tribunal_version is None
    assert "alpha" in rs.classes
    assert "beta" in rs.classes
    assert len(rs.classes) == 2
    assert "proc_test" in rs.procedures
    assert len(rs.tie_breakers) == 1


# --- Test: load with overlay -------------------------------------------------


def test_load_with_overlay(test_rules_dir: Path) -> None:
    """Loading with a tribunal overlay should merge correctly."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)

    assert rs.tribunal_id == "test-tribunal"
    assert rs.tribunal_version == "0.0.1-test"
    assert rs.core_version == "0.0.1-test"
    assert "alpha" in rs.classes
    assert "beta" in rs.classes
    assert "proc_test" in rs.procedures


# --- Test: append patterns ---------------------------------------------------


def test_append_patterns(test_rules_dir: Path) -> None:
    """Overlay without _replace should append patterns."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)
    alpha = rs.classes["alpha"]

    # Core has \\bALPHA_STRONG\\b, overlay appends \\bALPHA_LOCAL\\b
    pattern_strs = [p.pattern for p in alpha.strong_patterns]
    assert "\\bALPHA_STRONG\\b" in pattern_strs
    assert "\\bALPHA_LOCAL\\b" in pattern_strs
    assert len(alpha.strong_patterns) == 2


# --- Test: replace patterns --------------------------------------------------


def test_replace_patterns(test_rules_dir: Path) -> None:
    """Overlay with _replace should replace the entire pattern list."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)
    beta = rs.classes["beta"]

    # Core had \\bBETA_STRONG\\b, overlay replaces with \\bBETA_REPLACED\\b
    pattern_strs = [p.pattern for p in beta.strong_patterns]
    assert pattern_strs == ["\\bBETA_REPLACED\\b"]


# --- Test: globals override --------------------------------------------------


def test_globals_override(test_rules_dir: Path) -> None:
    """Overlay globals should deep-merge with core globals."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)

    # Core has class_keep_min=0.7, overlay sets 0.8
    assert rs.globals["confidence"]["class_keep_min"] == 0.8
    # Core-only keys should persist
    assert rs.globals["normalize_accents"] is True


# --- Test: invalid regex fails fast ------------------------------------------


def test_invalid_regex_fails_fast(test_rules_dir: Path) -> None:
    """A bad regex pattern should raise RulesetCompilationError immediately."""
    core_path = test_rules_dir / "core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["tabs"]["CLASSES"][0]["patterns"]["strong"].append("[invalid(")
    core_path.write_text(json.dumps(core), encoding="utf-8")

    with pytest.raises(RulesetCompilationError, match="invalid"):
        load_ruleset("core", rules_dir=test_rules_dir)


# --- Test: missing tribunal fails --------------------------------------------


def test_missing_tribunal_fails(test_rules_dir: Path) -> None:
    """Loading a nonexistent tribunal should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_ruleset("tce-nonexistent", rules_dir=test_rules_dir)


# --- Test: hash is deterministic ---------------------------------------------


def test_hash_deterministic(test_rules_dir: Path) -> None:
    """Same input should always produce the same hash."""
    rs1 = load_ruleset("test-tribunal", rules_dir=test_rules_dir)
    rs2 = load_ruleset("test-tribunal", rules_dir=test_rules_dir)

    assert rs1.ruleset_hash == rs2.ruleset_hash
    assert len(rs1.ruleset_hash) == 64  # SHA256 hex


# --- Test: required fields ---------------------------------------------------


def test_required_fields_class(test_rules_dir: Path) -> None:
    """A class missing required fields should raise RulesetCompilationError."""
    core_path = test_rules_dir / "core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    del core["tabs"]["CLASSES"][0]["confidence_rules"]
    core_path.write_text(json.dumps(core), encoding="utf-8")

    with pytest.raises(RulesetCompilationError, match="confidence_rules"):
        load_ruleset("core", rules_dir=test_rules_dir)


# --- Test: patterns are pre-compiled -----------------------------------------


def test_patterns_precompiled(test_rules_dir: Path) -> None:
    """All patterns in compiled classes should be re.Pattern instances."""
    rs = load_ruleset("core", rules_dir=test_rules_dir)

    for cls in rs.classes.values():
        for p in cls.strong_patterns:
            assert isinstance(p, re.Pattern)
        for p in cls.weak_patterns:
            assert isinstance(p, re.Pattern)
        for p in cls.negative_patterns:
            assert isinstance(p, re.Pattern)

    for proc in rs.procedures.values():
        for p in proc.strong_patterns:
            assert isinstance(p, re.Pattern)


# --- Test: dedupe on append --------------------------------------------------


def test_append_dedupe(test_rules_dir: Path) -> None:
    """Appending a pattern that already exists in core should not duplicate it."""
    overlay_path = test_rules_dir / "tribunals" / "test-tribunal.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    # Add a duplicate of core's pattern
    overlay["tabs"]["CLASSES"][0]["patterns"]["strong"].append("\\bALPHA_STRONG\\b")
    overlay_path.write_text(json.dumps(overlay), encoding="utf-8")

    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)
    alpha = rs.classes["alpha"]

    pattern_strs = [p.pattern for p in alpha.strong_patterns]
    assert pattern_strs.count("\\bALPHA_STRONG\\b") == 1


# --- Test: tie breakers merge (core + overlay) --------------------------------


def test_tie_breakers_merge(test_rules_dir: Path) -> None:
    """Core TIE_BREAKERS + overlay TIE_BREAKERS should both be present."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)

    ids = [tb["id"] for tb in rs.tie_breakers]
    assert "tb_core_test" in ids
    assert "tb_overlay_test" in ids
    assert len(rs.tie_breakers) == 2


# --- Test: tie breaker regex validated ----------------------------------------


def test_tie_breaker_invalid_regex(test_rules_dir: Path) -> None:
    """Invalid regex in TIE_BREAKERS should fail fast."""
    core_path = test_rules_dir / "core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["tabs"]["TIE_BREAKERS"][0]["when_any"][0]["regex"] = "[bad("
    core_path.write_text(json.dumps(core), encoding="utf-8")

    with pytest.raises(RulesetCompilationError, match="invalid"):
        load_ruleset("core", rules_dir=test_rules_dir)


# --- Test: procedures merge ---------------------------------------------------


def test_procedures_merge(test_rules_dir: Path) -> None:
    """Overlay should append patterns to procedures."""
    rs = load_ruleset("test-tribunal", rules_dir=test_rules_dir)
    proc = rs.procedures["proc_test"]

    pattern_strs = [p.pattern for p in proc.strong_patterns]
    assert "\\bTEST_PROC\\b" in pattern_strs
    assert "\\bTEST_PROC_LOCAL\\b" in pattern_strs


# --- Test: compiled class fields ----------------------------------------------


def test_compiled_class_fields(test_rules_dir: Path) -> None:
    """CompiledClass should have all expected fields."""
    rs = load_ruleset("core", rules_dir=test_rules_dir)
    alpha = rs.classes["alpha"]

    assert alpha.id == "alpha"
    assert alpha.label == "Alpha Class"
    assert alpha.priority == 80
    assert alpha.enabled is True
    assert alpha.whitelist is True
    assert alpha.confidence_rules["strong_hit"] == 0.95
    assert alpha.sources_priority == ["text_head", "ementa"]


# --- Test: production rules load successfully --------------------------------


def test_production_core_loads() -> None:
    """The actual rules/core.json should compile without errors."""
    rs = load_ruleset("core")
    assert len(rs.classes) == 14
    assert rs.core_version == "1.0.0"
    assert len(rs.procedures) == 1
    assert "exame_previo_edital" in rs.procedures
    assert len(rs.tie_breakers) >= 9
    assert len(rs.discard_rules) == 1


def test_production_tce_sp_loads() -> None:
    """The actual rules/tribunals/tce-sp.json should merge and compile."""
    rs = load_ruleset("tce-sp")
    assert rs.tribunal_id == "tce-sp"
    assert rs.tribunal_version == "1.0.0"
    assert len(rs.classes) == 14

    # TCE-SP overlay should have added patterns to representacao
    rep = rs.classes["representacao"]
    pattern_strs = [p.pattern for p in rep.strong_patterns]
    assert any("REPRESENTAD" in p for p in pattern_strs)

    # TCE-SP overlay adds tie-breakers
    tb_ids = [tb["id"] for tb in rs.tie_breakers]
    assert "tce_sp_epe_does_not_override_representacao" in tb_ids
    assert "tce_sp_epe_alone_add_procedure" in tb_ids

    # Core tie-breakers should also be present
    assert "tb_repr_by_parties_header" in tb_ids
