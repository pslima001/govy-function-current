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
        source_mode="batch_from_raw_pdfs",
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
    "tce-pr": TribunalConfig(
        tribunal_id="tce-pr",
        display_name="TCE-PR",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-pr/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-pr/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="PR",
        enabled=True,
    ),
    "tce-es": TribunalConfig(
        tribunal_id="tce-es",
        display_name="TCE-ES",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-es/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-es/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="ES",
        enabled=True,
    ),
    "tce-pa": TribunalConfig(
        tribunal_id="tce-pa",
        display_name="TCE-PA",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-pa/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-pa/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="PA",
        enabled=True,
    ),
    "tce-ce": TribunalConfig(
        tribunal_id="tce-ce",
        display_name="TCE-CE",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-ce/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-ce/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="CE",
        enabled=True,
    ),
    "tce-pb": TribunalConfig(
        tribunal_id="tce-pb",
        display_name="TCE-PB",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-pb/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-pb/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="PB",
        enabled=True,
    ),
    "tce-am": TribunalConfig(
        tribunal_id="tce-am",
        display_name="TCE-AM",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tce-am/acordaos/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tce-am/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="AM",
        enabled=True,
    ),
    "tcm-sp": TribunalConfig(
        tribunal_id="tcm-sp",
        display_name="TCM-SP",
        source_mode="batch_from_raw_pdfs",
        storage_account_raw="sttcejurisprudencia",
        container_raw="juris-raw",
        raw_prefix="tcm-sp/",
        storage_account_parsed="stgovyparsetestsponsor",
        container_parsed="juris-parsed",
        parsed_prefix="tcm-sp/",
        parser_id="tce_parser_v3",
        text_strategy="head",
        authority_score=0.80,
        uf="SP",
        enabled=True,
    ),
}


def get_config(tribunal_id: str) -> TribunalConfig:
    cfg = TRIBUNAL_CONFIGS.get(tribunal_id)
    if cfg is None:
        raise ValueError(f"Tribunal desconhecido: {tribunal_id}. Validos: {list(TRIBUNAL_CONFIGS.keys())}")
    return cfg
