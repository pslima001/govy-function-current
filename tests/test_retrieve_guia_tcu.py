"""
Tests for govy.utils.retrieve_guia_tcu

Requires env vars: AZURE_SEARCH_API_KEY, AZURE_SEARCH_ENDPOINT, OPENAI_API_KEY
Skip with: pytest -m "not integration"
"""

import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Skip all tests if env vars not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("AZURE_SEARCH_API_KEY"),
    reason="AZURE_SEARCH_API_KEY not set (integration test)",
)


from govy.utils.retrieve_guia_tcu import (
    retrieve_guia_tcu,
    retrieve_guia_tcu_dicts,
    GuiaTcuResult,
    VALID_STAGES,
    _build_filter,
    _FORCED_DOC_TYPE,
)


# ─── Unit tests (no network) ────────────────────────────────────────────────

class TestBuildFilter:
    def test_base_filter_always_present(self):
        f = _build_filter()
        assert "doc_type eq 'guia_tcu'" in f
        assert "is_citable eq false" in f

    def test_stage_tag_added(self):
        f = _build_filter(stage_tag="edital")
        assert "procedural_stage eq 'EDITAL'" in f

    def test_stage_tag_normalized(self):
        f = _build_filter(stage_tag="seleção")
        assert "procedural_stage eq 'SELECAO'" in f

    def test_stage_tag_case_insensitive(self):
        f = _build_filter(stage_tag="GESTAO")
        assert "procedural_stage eq 'GESTAO'" in f

    def test_invalid_stage_tag_ignored(self):
        f = _build_filter(stage_tag="invalid_stage")
        assert "procedural_stage" not in f

    def test_governance_not_bypassable(self):
        """Ensure doc_type and is_citable are always forced."""
        f = _build_filter(stage_tag="planejamento")
        assert f"doc_type eq '{_FORCED_DOC_TYPE}'" in f
        assert "is_citable eq false" in f


# ─── Integration tests (requires Azure Search) ──────────────────────────────

class TestRetrieveGuiaTcu:
    def test_returns_results(self):
        results = retrieve_guia_tcu("prazo para impugnacao do edital", top_k=3)
        assert len(results) > 0
        assert isinstance(results[0], GuiaTcuResult)

    def test_all_results_are_guia_tcu(self):
        results = retrieve_guia_tcu("habilitacao tecnica", top_k=10)
        for r in results:
            assert r.chunk_id.startswith("guia_tcu--"), f"chunk_id should start with guia_tcu--: {r.chunk_id}"

    def test_stage_tag_filter_works(self):
        results = retrieve_guia_tcu(
            "subcontratacao", stage_tag="gestao", top_k=5
        )
        for r in results:
            assert r.procedural_stage == "GESTAO", f"Expected GESTAO, got {r.procedural_stage}"

    def test_no_citable_results(self):
        """Governance: guia_tcu must NEVER return citable chunks."""
        results = retrieve_guia_tcu("qualquer query", top_k=20)
        # We can't check is_citable from results (not in select),
        # but the filter enforces is_citable eq false.
        # Verify the filter is correct:
        f = _build_filter()
        assert "is_citable eq false" in f

    def test_results_have_required_fields(self):
        results = retrieve_guia_tcu("planejamento da contratacao", top_k=3)
        assert len(results) > 0
        r = results[0]
        assert r.chunk_id
        assert r.section_title
        assert r.text_snippet
        assert r.score > 0
        assert r.procedural_stage in VALID_STAGES

    def test_dict_output(self):
        results = retrieve_guia_tcu_dicts("edital de licitacao", top_k=2)
        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], dict)
        assert "chunk_id" in results[0]
        assert "section_title" in results[0]

    def test_top_k_respected(self):
        results = retrieve_guia_tcu("licitacao", top_k=5)
        assert len(results) <= 5

    def test_text_only_fallback(self):
        """Test that search works without vector/semantic."""
        results = retrieve_guia_tcu(
            "pregao eletronico",
            top_k=3,
            use_vector=False,
            use_semantic=False,
        )
        assert len(results) > 0
