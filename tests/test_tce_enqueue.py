"""Unit tests for tribunal registry + queue handler payload logic."""

import pytest

from govy.config.tribunal_registry import get_config
from govy.api.tce_queue_handler import _blob_path_to_json_key


# --- Registry config tests ---


def test_default_tribunal_is_tce_sp():
    cfg = get_config("tce-sp")
    assert cfg.tribunal_id == "tce-sp"
    assert cfg.container_raw == "juris-raw"
    assert cfg.raw_prefix == "tce-sp/"


def test_tce_mg_accepted():
    cfg = get_config("tce-mg")
    assert cfg.tribunal_id == "tce-mg"
    assert cfg.container_raw == "juris-raw"
    assert cfg.raw_prefix == "tce-mg/"
    assert cfg.uf == "MG"


def test_invalid_tribunal_raises():
    with pytest.raises(ValueError, match="Tribunal desconhecido"):
        get_config("tce-xx")


# --- json_key conversion tests ---


def test_blob_path_to_json_key_tce_mg():
    key = _blob_path_to_json_key("tce-mg/acordaos/1058903_acordao.pdf")
    assert key == "tce-mg--acordaos--1058903_acordao.json"


def test_blob_path_to_json_key_tce_sp():
    key = _blob_path_to_json_key("tce-sp/acordaos/10026_989_24_acordao.pdf")
    assert key == "tce-sp--acordaos--10026_989_24_acordao.json"


# --- tribunal_id inference tests ---


def test_tribunal_id_inferred_from_blob_path_mg():
    path = "tce-mg/acordaos/1058903_acordao.pdf"
    inferred = path.split("/")[0] if "/" in path else "tce-sp"
    assert inferred == "tce-mg"


def test_tribunal_id_inferred_from_blob_path_sp():
    path = "tce-sp/acordaos/10026_989_24_acordao.pdf"
    inferred = path.split("/")[0] if "/" in path else "tce-sp"
    assert inferred == "tce-sp"


def test_tribunal_id_fallback_no_slash():
    path = "orphan_file.pdf"
    inferred = path.split("/")[0] if "/" in path else "tce-sp"
    assert inferred == "tce-sp"


# --- TCM-SP registry tests ---


def test_tcm_sp_config():
    cfg = get_config("tcm-sp")
    assert cfg.tribunal_id == "tcm-sp"
    assert cfg.display_name == "TCM-SP"
    assert cfg.authority_score == 0.80
    assert cfg.uf == "SP"
    assert cfg.parser_id == "tce_parser_v3"
    assert cfg.text_strategy == "head"
    assert cfg.raw_prefix == "tcm-sp/"
    assert cfg.enabled is True


def test_blob_path_to_json_key_tcm_sp():
    key = _blob_path_to_json_key("tcm-sp/acordaos/tcm-sp--TC0032092006--811233.pdf")
    assert key == "tcm-sp--acordaos--tcm-sp--TC0032092006--811233.json"


# --- Pre-filter (step 2a): non-decision attachment detection ---


def _make_pdf_bytes(text: str) -> bytes:
    """Create a minimal valid PDF containing only the given text."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((10, 50), text, fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_prefilter_attachment_no_legal_markers(monkeypatch):
    """
    A PDF with no legal markers (EMENTA, DISPOSITIVO, ACORDAM, etc.)
    and parser returning all __MISSING__ content fields must produce
    status=terminal_skip, reason=non_decision_attachment.
    """
    from unittest.mock import MagicMock

    attachment_pdf = _make_pdf_bytes("LOTE 1 - VPL R$ 554.3 MM - FLUXO DE CAIXA 2018-2038")

    # Stub: _get_tce_blob_service → returns our attachment PDF
    mock_blob_client = MagicMock()
    mock_blob_client.download_blob.return_value.readall.return_value = attachment_pdf
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    mock_service = MagicMock()
    mock_service.get_container_client.return_value = mock_container

    monkeypatch.setattr(
        "govy.api.tce_queue_handler._get_tce_blob_service",
        lambda: mock_service,
    )

    # Stub: parse_pdf_bytes → all content fields __MISSING__
    all_missing = {
        "tribunal_type": "TCM",
        "tribunal_name": "TCM-SP",
        "uf": "SP",
        "region": "SUDESTE",
        "processo": "__MISSING__",
        "acordao_numero": "__MISSING__",
        "relator": "__MISSING__",
        "orgao_julgador": "__MISSING__",
        "ementa": "__MISSING__",
        "dispositivo": "__MISSING__",
        "key_citation": "__MISSING__",
        "holding_outcome": "__MISSING__",
        "effect": "__MISSING__",
        "year": "__MISSING__",
        "is_current": "__MISSING__",
        "authority_score": "__MISSING__",
        "procedural_stage": "__MISSING__",
        "publication_number": "__MISSING__",
        "publication_date": "__MISSING__",
        "julgamento_date": "__MISSING__",
        "references": [],
        "linked_processes": [],
        "claim_pattern": [],
        "key_citation_speaker": "__MISSING__",
        "key_citation_source": "__MISSING__",
    }
    monkeypatch.setattr(
        "govy.api.tce_parser_v3.parse_pdf_bytes",
        lambda *a, **kw: all_missing,
    )

    from govy.api.tce_queue_handler import handle_parse_tce_pdf

    msg = {
        "tribunal_id": "tcm-sp",
        "blob_path": "tcm-sp/acordaos/tcm-sp--TC0031042018--74776.pdf",
        "blob_etag": "0x0",
        "json_key": "tcm-sp--acordaos--tcm-sp--TC0031042018--74776.json",
    }

    result = handle_parse_tce_pdf(msg)

    assert result["status"] == "terminal_skip"
    assert result["reason"] == "non_decision_attachment"
    assert result["blob_path"] == msg["blob_path"]
    assert result["text_length"] > 0


def test_prefilter_passes_when_legal_markers_present(monkeypatch):
    """
    A PDF containing EMENTA or ACORDAM must NOT be caught by the pre-filter.
    The parser returns all __MISSING__ but the raw text has legal markers.
    """
    from unittest.mock import MagicMock

    legal_pdf = _make_pdf_bytes("EMENTA: Licitacao irregular. ACORDAM os Conselheiros.")

    mock_blob_client = MagicMock()
    mock_blob_client.download_blob.return_value.readall.return_value = legal_pdf
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    mock_service = MagicMock()
    mock_service.get_container_client.return_value = mock_container

    monkeypatch.setattr(
        "govy.api.tce_queue_handler._get_tce_blob_service",
        lambda: mock_service,
    )

    all_missing = {
        "tribunal_type": "TCM", "tribunal_name": "TCM-SP", "uf": "SP",
        "region": "SUDESTE", "processo": "__MISSING__",
        "acordao_numero": "__MISSING__", "relator": "__MISSING__",
        "orgao_julgador": "__MISSING__", "ementa": "__MISSING__",
        "dispositivo": "__MISSING__", "key_citation": "__MISSING__",
        "holding_outcome": "__MISSING__", "effect": "__MISSING__",
        "year": "__MISSING__", "is_current": "__MISSING__",
        "authority_score": "__MISSING__", "procedural_stage": "__MISSING__",
        "publication_number": "__MISSING__", "publication_date": "__MISSING__",
        "julgamento_date": "__MISSING__", "references": [],
        "linked_processes": [], "claim_pattern": [],
        "key_citation_speaker": "__MISSING__",
        "key_citation_source": "__MISSING__",
    }
    monkeypatch.setattr(
        "govy.api.tce_parser_v3.parse_pdf_bytes",
        lambda *a, **kw: all_missing,
    )

    # Stub mapping to return empty (no_content) — this is the fallback path
    monkeypatch.setattr(
        "govy.api.mapping_tce_to_kblegal.transform_parser_to_kblegal",
        lambda *a, **kw: {},
    )

    from govy.api.tce_queue_handler import handle_parse_tce_pdf

    msg = {
        "tribunal_id": "tcm-sp",
        "blob_path": "tcm-sp/acordaos/tcm-sp--TC9999992024--999999.pdf",
        "blob_etag": "0x0",
        "json_key": "tcm-sp--acordaos--tcm-sp--TC9999992024--999999.json",
    }

    result = handle_parse_tce_pdf(msg)

    # Must NOT be terminal_skip — the pre-filter should let it through
    assert result["status"] != "terminal_skip"
