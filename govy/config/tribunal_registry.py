"""Tribunal registry: config-driven definitions for each supported tribunal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TribunalConfig:
    tribunal_id: str
    display_name: str
    source_mode: str  # batch_from_raw_pdfs | scrape_pdf | import_json
    storage_account_raw: str
    container_raw: str
    raw_prefix: str
    storage_account_parsed: str
    container_parsed: str
    parsed_prefix: str
    parser_id: str
    text_strategy: str  # head | full_text
    authority_score: float
    uf: Optional[str]
    enabled: bool


TRIBUNAL_CONFIGS: Dict[str, TribunalConfig] = {
    "tce-sp": TribunalConfig(
        tribunal_id="tce-sp",
        display_name="TCE-SP",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-sp/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-sp/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="SP",
        enabled=True,
    ),
    "tcu": TribunalConfig(
        tribunal_id="tcu",
        display_name="TCU",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tcu/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tcu/",
        parser_id="tce_parser_v3",
        text_strategy="full_text",
        authority_score=0.90,
        uf=None,
        enabled=True,
    ),
    "tce-mg": TribunalConfig(
        tribunal_id="tce-mg",
        display_name="TCE-MG",
        source_mode="import_json",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-mg/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-mg/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="MG",
        enabled=True,
    ),
    "tce-sc": TribunalConfig(
        tribunal_id="tce-sc",
        display_name="TCE-SC",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-sc/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-sc/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="SC",
        enabled=True,
    ),
}


def get_config(tribunal_id: str) -> TribunalConfig:
    cfg = TRIBUNAL_CONFIGS.get(tribunal_id)
    if cfg is None:
        raise ValueError(f"Tribunal desconhecido: {tribunal_id}. Validos: {list(TRIBUNAL_CONFIGS.keys())}")
    return cfg
