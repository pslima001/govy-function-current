"""
Tests — Issue D: Governance regression — guia_tcu NEVER in citable/defense flows
==================================================================================
These tests ensure that doc_type="guia_tcu" chunks NEVER appear in:
- Defense retrieval (kb_search golden path)
- Any citable result set
- Any flow that generates citations for licitante arguments

The guia_tcu is ONLY accessible through the dedicated retrieve_guia_tcu
retriever with forced filters (doc_type='guia_tcu', is_citable=false).

Skip integration tests with: pytest -m "not integration"
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# kb_search.py imports azure.functions at module level which is not available
# locally. We use source-file reading for static analysis tests instead.
_KB_SEARCH_PATH = os.path.join(
    os.path.dirname(__file__), "..", "govy", "api", "kb_search.py"
)


def _read_kb_search_source() -> str:
    with open(_KB_SEARCH_PATH, encoding="utf-8") as f:
        return f.read()


# ─── Unit Tests (no network) ──────────────────────────────────────────────────

class TestGovernanceKbSearchFilters:
    """Verify kb_search.py defense flow NEVER queries guia_tcu (static analysis)."""

    def test_defense_hardcoded_doc_type(self):
        """The golden-path search_with_jurisdiction always uses doc_type='jurisprudencia'."""
        source = _read_kb_search_source()
        assert 'doc_type="jurisprudencia"' in source, (
            "search_with_jurisdiction_fallback must hardcode doc_type='jurisprudencia'"
        )

    def test_kb_search_never_references_guia_tcu(self):
        """kb_search.py must NOT contain any reference to guia_tcu."""
        source = _read_kb_search_source()
        assert "guia_tcu" not in source, (
            "kb_search must not reference guia_tcu anywhere"
        )

    def test_kb_search_never_imports_retrieve_guia(self):
        """kb_search.py must not import retrieve_guia_tcu."""
        source = _read_kb_search_source()
        assert "retrieve_guia_tcu" not in source, (
            "kb_search must not import or reference retrieve_guia_tcu"
        )


class TestGovernanceRetrieveGuiaTcuFilters:
    """Verify retrieve_guia_tcu ALWAYS forces governance filters."""

    def test_forced_doc_type(self):
        from govy.utils.retrieve_guia_tcu import _build_filter, _FORCED_DOC_TYPE
        f = _build_filter()
        assert f"doc_type eq '{_FORCED_DOC_TYPE}'" in f
        assert _FORCED_DOC_TYPE == "guia_tcu"

    def test_forced_is_citable_false(self):
        from govy.utils.retrieve_guia_tcu import _build_filter
        f = _build_filter()
        assert "is_citable eq false" in f

    def test_cannot_override_governance(self):
        """_build_filter only accepts stage_tag — no way to change doc_type or is_citable."""
        import inspect
        from govy.utils.retrieve_guia_tcu import _build_filter
        sig = inspect.signature(_build_filter)
        params = list(sig.parameters.keys())
        # Only stage_tag is accepted
        assert params == ["stage_tag"], (
            f"_build_filter should only accept stage_tag, got: {params}"
        )

    def test_governance_with_all_stage_tags(self):
        """Governance filters must be present regardless of stage_tag."""
        from govy.utils.retrieve_guia_tcu import _build_filter, VALID_STAGES
        for stage in [None, "edital", "planejamento", "contrato", "gestão", "seleção", "governança"]:
            f = _build_filter(stage_tag=stage)
            assert "doc_type eq 'guia_tcu'" in f, f"doc_type missing for stage={stage}"
            assert "is_citable eq false" in f, f"is_citable missing for stage={stage}"


class TestGovernanceNoLeakage:
    """Verify the two paths (defense vs checklist) are completely separated."""

    def test_retrieve_guia_tcu_module_does_not_import_kb_search(self):
        """guia_tcu retriever must NOT depend on kb_search (separation of concerns)."""
        import inspect
        from govy.utils import retrieve_guia_tcu as mod
        source = inspect.getsource(mod)
        assert "kb_search" not in source, (
            "retrieve_guia_tcu must not import or reference kb_search"
        )

    def test_kb_search_does_not_import_guia_tcu(self):
        """kb_search must NOT depend on retrieve_guia_tcu (separation of concerns)."""
        source = _read_kb_search_source()
        assert "retrieve_guia_tcu" not in source, (
            "kb_search must not import or reference retrieve_guia_tcu"
        )
        assert "guia_tcu" not in source, (
            "kb_search must not reference guia_tcu anywhere"
        )

    def test_checklist_generator_uses_correct_retriever(self):
        """Checklist generator must use retrieve_guia_tcu, not kb_search."""
        import inspect
        from govy.checklist import generator as mod
        source = inspect.getsource(mod)
        assert "retrieve_guia_tcu" in source, (
            "generator must use retrieve_guia_tcu for references"
        )
        assert "kb_search" not in source, (
            "generator must NOT use kb_search (defense path)"
        )

    def test_audit_questions_are_pure_data(self):
        """audit_questions.py must have no imports from api or search modules."""
        import inspect
        from govy.checklist import audit_questions as mod
        source = inspect.getsource(mod)
        assert "kb_search" not in source
        assert "retrieve_guia_tcu" not in source
        assert "SearchClient" not in source


# ─── Integration Tests (requires Azure Search) ───────────────────────────────

pytestmark_integration = pytest.mark.skipif(
    not os.environ.get("AZURE_SEARCH_API_KEY"),
    reason="AZURE_SEARCH_API_KEY not set (integration test)",
)


@pytestmark_integration
class TestGovernanceLiveIndex:
    """Live checks against the kb-legal index."""

    def test_guia_tcu_not_in_defense_results(self):
        """Defense search (doc_type=jurisprudencia) must return 0 guia_tcu chunks."""
        from govy.api.kb_search import build_filter, execute_search_attempt
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
        api_key = os.environ.get("AZURE_SEARCH_API_KEY")
        client = SearchClient(
            endpoint=endpoint,
            index_name="kb-legal",
            credential=AzureKeyCredential(api_key),
        )

        filter_str = build_filter(doc_type="jurisprudencia")
        results, count, error = execute_search_attempt(
            client, "licitação pregão", None, filter_str,
            top_k=50, use_semantic=False, use_vector=False,
        )
        for r in results:
            chunk_id = r.get("chunk_id", "")
            assert not chunk_id.startswith("guia_tcu"), (
                f"guia_tcu chunk leaked into defense results: {chunk_id}"
            )

    def test_guia_tcu_retriever_returns_only_guia(self):
        """Dedicated retriever must return ONLY guia_tcu chunks."""
        from govy.utils.retrieve_guia_tcu import retrieve_guia_tcu
        results = retrieve_guia_tcu("prazo impugnação edital", top_k=20)
        for r in results:
            assert r.chunk_id.startswith("guia_tcu--"), (
                f"Non-guia_tcu chunk in retriever results: {r.chunk_id}"
            )

    def test_cross_contamination_impossible(self):
        """
        Query the same text through both paths — results must be completely disjoint.
        This is the ultimate governance test.
        """
        from govy.api.kb_search import build_filter, execute_search_attempt
        from govy.utils.retrieve_guia_tcu import retrieve_guia_tcu
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://search-govy-kb.search.windows.net")
        api_key = os.environ.get("AZURE_SEARCH_API_KEY")
        client = SearchClient(
            endpoint=endpoint,
            index_name="kb-legal",
            credential=AzureKeyCredential(api_key),
        )

        query = "habilitação técnica licitação"

        # Defense path
        filter_str = build_filter(doc_type="jurisprudencia")
        defense_results, _, _ = execute_search_attempt(
            client, query, None, filter_str,
            top_k=20, use_semantic=False, use_vector=False,
        )
        defense_ids = {r.get("chunk_id", "") for r in defense_results}

        # Checklist path
        guia_results = retrieve_guia_tcu(
            query, top_k=20, use_vector=False, use_semantic=False,
        )
        guia_ids = {r.chunk_id for r in guia_results}

        # Zero overlap
        overlap = defense_ids & guia_ids
        assert len(overlap) == 0, (
            f"CRITICAL: {len(overlap)} chunks appear in BOTH defense and guia paths: {overlap}"
        )
