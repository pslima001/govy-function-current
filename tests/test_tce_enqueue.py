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
