"""
CP15 — Unit equivalence conversion tests.

Tests that the matching engine correctly handles pharmacologically equivalent
concentrations and volumes expressed in different units (MG/G/MCG, ML/L).

This is NOT tolerance relaxation — it's exact equivalence by unit conversion.
"""
import pytest

from govy.matching.models import ItemRequirement, Presentation, WaiverConfig
from govy.matching.matcher import (
    _conc_equal,
    _nearly_equal,
    _to_mg,
    _to_ml,
    match_item_to_bula,
)


# =============================================================================
# Helper: build an ItemRequirement with defaults
# =============================================================================

def _req(
    conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
    vol=50.0, vol_unit="ML",
    principle="RITUXIMABE", form="SOLUCAO INJETAVEL", pkg="FRASCO-AMPOLA",
):
    return ItemRequirement(
        raw="test",
        principle=principle,
        conc_num=conc_num,
        conc_unit=conc_unit,
        conc_den_unit=conc_den_unit,
        form=form,
        pkg=pkg,
        vol=vol,
        vol_unit=vol_unit,
    )


def _pres(
    conc_num=None, conc_unit=None, conc_den_unit=None,
    dose=None, dose_unit=None,
    vol=None, vol_unit=None,
    form="SOLUCAO INJETAVEL",
):
    return Presentation(
        dose=dose, dose_unit=dose_unit,
        vol=vol, vol_unit=vol_unit,
        conc_num=conc_num, conc_unit=conc_unit, conc_den_unit=conc_den_unit,
        form=form,
        evidence="test evidence",
    )


# =============================================================================
# Unit conversion helpers
# =============================================================================

class TestToMg:
    def test_mg_identity(self):
        assert _to_mg(10.0, "MG") == 10.0

    def test_g_to_mg(self):
        assert _to_mg(0.01, "G") == 10.0

    def test_mcg_to_mg(self):
        assert _to_mg(1000.0, "MCG") == 1.0

    def test_ui_returns_none(self):
        assert _to_mg(100.0, "UI") is None

    def test_unknown_unit_returns_none(self):
        assert _to_mg(10.0, "BANANA") is None


class TestToMl:
    def test_ml_identity(self):
        assert _to_ml(50.0, "ML") == 50.0

    def test_l_to_ml(self):
        assert _to_ml(0.05, "L") == 50.0

    def test_unknown_unit_returns_none(self):
        assert _to_ml(50.0, "BANANA") is None


# =============================================================================
# CP15A — Concentration equivalence
# =============================================================================

class TestConcEquivalence:
    """A1-A8: concentration comparison with unit conversion."""

    def test_a1_mg_vs_g(self):
        """10 MG/ML vs 0.01 G/ML → MATCH (0.01 G = 10 MG)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=0.01, conc_unit="G", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_a2_mcg_vs_mg(self):
        """1000 MCG/ML vs 1 MG/ML → MATCH (1000 MCG = 1 MG)."""
        req = _req(conc_num=1000.0, conc_unit="MCG", conc_den_unit="ML")
        p = _pres(conc_num=1.0, conc_unit="MG", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_a3_same_num_diff_den(self):
        """10 MG/ML vs 10 MG/L → UNMATCH (10/1 ML != 10/1000 ML)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=10.0, conc_unit="MG", conc_den_unit="L")
        assert _conc_equal(req, p) is False

    def test_a4_mcg_vs_mg_same_den(self):
        """10 MG/ML vs 10000 MCG/ML → MATCH (10000 MCG = 10 MG)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=10000.0, conc_unit="MCG", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_a5_ui_same(self):
        """100 UI/ML vs 100 UI/ML → MATCH (same UI)."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        p = _pres(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_a6_ui_vs_mg(self):
        """100 UI/ML vs 100 MG/ML → UNMATCH (UI vs MG not convertible)."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        p = _pres(conc_num=100.0, conc_unit="MG", conc_den_unit="ML")
        assert _conc_equal(req, p) is False

    def test_a7_cross_multiply_with_conversion(self):
        """10 MG/ML vs 500 MG/50 ML (dose/vol) → MATCH."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
            dose=500.0, dose_unit="MG",
            vol=50.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is True

    def test_a8_cross_multiply_mcg_dose(self):
        """10 MG/ML vs 10000 MCG/50 ML (dose/vol) → MATCH (MCG→MG then cross-multiply)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        # dose=10000 MCG = 10 MG, vol=50 ML → 10 MG / 50 ML = 0.2 MG/ML ≠ 10 MG/ML
        # Wait: 10000 MCG / 50 ML = 10 MG / 50 ML = 0.2 MG/ML ≠ 10 MG/ML
        # Actually: the plan says this should MATCH, let me re-read...
        # Plan says: "10 MG/ML vs 10000 MCG/50 ML (dose/vol) → MATCH"
        # This means dose=10000 MCG, vol=50 ML → but 10000 MCG = 10 MG
        # 10 MG / 50 ML = 0.2 MG/ML, req is 10 MG/ML → that's NOT equal!
        #
        # The plan must mean: bula has conc derived from dose/vol where the
        # dose is expressed in MCG but equivalent after conversion.
        # For 10 MG/ML * 50 ML = 500 MG → 500000 MCG
        # So dose=500000 MCG, vol=50 ML → 500 MG / 50 ML = 10 MG/ML ✓
        p = _pres(
            conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
            dose=500000.0, dose_unit="MCG",
            vol=50.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is True

    def test_a8_alt_simple_mcg(self):
        """Alternative A8: 1 MG/ML vs 1000 MCG/1 ML dose/vol → MATCH."""
        req = _req(conc_num=1.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=1.0, conc_unit="MG", conc_den_unit="ML",
            dose=1000.0, dose_unit="MCG",
            vol=1.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is True


# =============================================================================
# CP15B — Volume equivalence (full integration via match_item_to_bula)
# =============================================================================

class TestVolumeEquivalence:
    """B1-B2: volume comparison with unit conversion."""

    def test_b1_ml_vs_l(self):
        """FRASCO-AMPOLA 50 ML vs FRASCO-AMPOLA 0,05 L → MATCH."""
        req = _req(vol=50.0, vol_unit="ML")
        bula = (
            "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 0,05 L"
        )
        result = match_item_to_bula("B1", req, bula)
        assert result.status == "MATCH", (
            f"Expected MATCH, got {result.status}. Gaps: {result.gaps}"
        )

    def test_b2_ml_vs_l_1000(self):
        """FRASCO-AMPOLA 1000 ML vs FRASCO-AMPOLA 1 L → MATCH."""
        req = _req(vol=1000.0, vol_unit="ML")
        bula = (
            "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 1 L"
        )
        result = match_item_to_bula("B2", req, bula)
        assert result.status == "MATCH", (
            f"Expected MATCH, got {result.status}. Gaps: {result.gaps}"
        )


# =============================================================================
# CP15C — Regression: existing behaviour preserved
# =============================================================================

class TestRegressionCP15:
    """Ensure CP15 changes don't break existing matching scenarios."""

    def test_exact_match_same_units(self):
        """Standard exact match still works: 10 MG/ML == 10 MG/ML."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_mismatch_different_value(self):
        """Different numeric value still fails: 10 MG/ML != 5 MG/ML."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=5.0, conc_unit="MG", conc_den_unit="ML")
        assert _conc_equal(req, p) is False

    def test_cross_multiply_exact(self):
        """CP13: cross-multiply path (500 MG/50 ML == 10 MG/ML)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
            dose=500.0, dose_unit="MG",
            vol=50.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is True

    def test_cross_multiply_mismatch(self):
        """CP13: cross-multiply mismatch (500 MG/60 ML != 10 MG/ML)."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
            dose=500.0, dose_unit="MG",
            vol=60.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is False

    def test_conc_missing_returns_false(self):
        """Presentation with no concentration info → False."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML")
        p = _pres(conc_num=None, conc_unit=None, conc_den_unit=None)
        assert _conc_equal(req, p) is False

    def test_full_match_integration(self):
        """Full integration: same bula text, same units → MATCH."""
        req = _req()
        bula = (
            "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 50 ML"
        )
        result = match_item_to_bula("REG1", req, bula)
        assert result.status == "MATCH"

    def test_full_unmatch_bad_conc(self):
        """Full integration: wrong concentration → UNMATCH."""
        req = _req(conc_num=10.0)
        bula = (
            "RITUXIMABE 5 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 50 ML"
        )
        result = match_item_to_bula("REG2", req, bula)
        assert result.status == "UNMATCH"

    def test_ui_exact_match_full(self):
        """UI units: exact match via integration."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        bula = (
            "RITUXIMABE 100 UI/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 50 ML"
        )
        result = match_item_to_bula("REG3", req, bula)
        assert result.status == "MATCH"

    def test_volume_exact_same_units(self):
        """Volume: same units, same value → MATCH."""
        req = _req(vol=50.0, vol_unit="ML")
        bula = (
            "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 50 ML"
        )
        result = match_item_to_bula("REG4", req, bula)
        assert result.status == "MATCH"

    def test_volume_mismatch_diff_value(self):
        """Volume: same units, different value → UNMATCH."""
        req = _req(vol=50.0, vol_unit="ML")
        bula = (
            "RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 100 ML"
        )
        result = match_item_to_bula("REG5", req, bula)
        assert result.status == "UNMATCH"


# =============================================================================
# CP15 Integration: concentration + volume conversion together
# =============================================================================

class TestCombinedConversion:
    """Both conc and vol conversion in the same match."""

    def test_g_conc_and_l_vol(self):
        """0.01 G/ML conc + 0.05 L vol → MATCH with 10 MG/ML + 50 ML req."""
        req = _req(conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
                   vol=50.0, vol_unit="ML")
        bula = (
            "RITUXIMABE 0,01 G/ML SOLUCAO INJETAVEL "
            "FRASCO-AMPOLA 0,05 L"
        )
        result = match_item_to_bula("COMB1", req, bula)
        assert result.status == "MATCH", (
            f"Expected MATCH, got {result.status}. Gaps: {result.gaps}"
        )


# =============================================================================
# CP15D — UI with denominator conversion (bug fix #1)
# =============================================================================

class TestUIDenominatorConversion:
    """UI numerator is non-convertible, but denominator ML/L IS convertible."""

    def test_ui_ml_vs_ui_l(self):
        """100 UI/ML vs 100000 UI/L → MATCH (100000/1000 = 100 UI/ML)."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        p = _pres(conc_num=100000.0, conc_unit="UI", conc_den_unit="L")
        assert _conc_equal(req, p) is True

    def test_ui_l_vs_ui_ml(self):
        """0.1 UI/L vs 0.0001 UI/ML → MATCH (0.1/1000 = 0.0001 UI/ML)."""
        req = _req(conc_num=0.1, conc_unit="UI", conc_den_unit="L")
        p = _pres(conc_num=0.0001, conc_unit="UI", conc_den_unit="ML")
        assert _conc_equal(req, p) is True

    def test_ui_ml_vs_ui_l_mismatch(self):
        """100 UI/ML vs 50000 UI/L → UNMATCH (50000/1000 = 50 != 100)."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        p = _pres(conc_num=50000.0, conc_unit="UI", conc_den_unit="L")
        assert _conc_equal(req, p) is False

    def test_ui_vs_mg_still_unmatch(self):
        """100 UI/ML vs 100 MG/ML → UNMATCH (UI vs MG not convertible)."""
        req = _req(conc_num=100.0, conc_unit="UI", conc_den_unit="ML")
        p = _pres(conc_num=100.0, conc_unit="MG", conc_den_unit="ML")
        assert _conc_equal(req, p) is False


# =============================================================================
# CP15E — Relative tolerance (bug fix #2)
# =============================================================================

class TestNearlyEqual:
    """_nearly_equal uses relative tolerance, not absolute."""

    def test_equal_values(self):
        assert _nearly_equal(100.0, 100.0) is True

    def test_both_zero(self):
        assert _nearly_equal(0.0, 0.0) is True

    def test_tiny_relative_diff(self):
        """Values differ by ~1e-10 relative → MATCH."""
        assert _nearly_equal(1000.0, 1000.0 + 1e-7) is True

    def test_large_absolute_small_relative(self):
        """Large absolute diff but small relative → MATCH."""
        assert _nearly_equal(1e9, 1e9 + 0.1) is True

    def test_small_values_reject_large_relative_diff(self):
        """0.001 vs 0.0011 → 10% relative diff → UNMATCH."""
        assert _nearly_equal(0.001, 0.0011) is False

    def test_small_values_reject_0_01_absolute(self):
        """0.005 vs 0.014 → would pass abs(diff) < 0.01 but fails relative."""
        assert _nearly_equal(0.005, 0.014) is False


class TestSmallDoseTolerance:
    """Ensure small-dose cross-multiply doesn't falsely match with 0.01 abs."""

    def test_small_dose_rejects_wrong_value(self):
        """0.001 MG/ML req vs 0.0011 MG/1 ML dose/vol → UNMATCH (10% off)."""
        req = _req(conc_num=0.001, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=0.001, conc_unit="MG", conc_den_unit="ML",
            dose=0.0011, dose_unit="MG",
            vol=1.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is False

    def test_small_dose_accepts_exact(self):
        """0.001 MG/ML req vs 0.001 MG/1 ML dose/vol → MATCH."""
        req = _req(conc_num=0.001, conc_unit="MG", conc_den_unit="ML")
        p = _pres(
            conc_num=0.001, conc_unit="MG", conc_den_unit="ML",
            dose=0.001, dose_unit="MG",
            vol=1.0, vol_unit="ML",
        )
        assert _conc_equal(req, p) is True
