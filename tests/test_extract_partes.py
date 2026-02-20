"""Tests for extract_partes in tce_parser_v3 — party extraction from TCE headers."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.api.tce_parser_v3 import extract_partes, parse_text, MISSING


# ── Original 25 keys — regression guard (req F) ───────────────────────────────

ORIGINAL_25_KEYS = {
    "tribunal_type", "tribunal_name", "uf", "region",
    "processo", "acordao_numero", "relator", "orgao_julgador",
    "ementa", "dispositivo", "holding_outcome", "effect",
    "publication_number", "publication_date", "julgamento_date",
    "references", "linked_processes", "procedural_stage",
    "claim_pattern", "authority_score", "year", "is_current",
    "key_citation", "key_citation_speaker", "key_citation_source",
}


def test_parse_text_original_keys_present():
    """All 25 original keys must still be top-level."""
    text = "TRIBUNAL DE CONTAS\nEMENTA: Consulta.\nACORDAM em responder a consulta."
    result = parse_text(text)
    for key in ORIGINAL_25_KEYS:
        assert key in result, f"Missing original key: {key}"


def test_parse_text_no_extra_top_level_keys():
    """Only original 25 + party_extraction (nested). No other new top-level keys."""
    text = "TRIBUNAL DE CONTAS\nEMENTA: Consulta.\nACORDAM."
    result = parse_text(text)
    allowed = ORIGINAL_25_KEYS | {"party_extraction"}
    extra = set(result.keys()) - allowed
    assert extra == set(), f"Unexpected top-level keys: {extra}"


def test_party_extraction_structure():
    """party_extraction must be a dict with version, partes, partes_privadas, partes_publicas."""
    text = "TRIBUNAL DE CONTAS\nEMENTA: Consulta."
    result = parse_text(text)
    pe = result["party_extraction"]
    assert isinstance(pe, dict)
    assert pe["version"] == 1
    assert isinstance(pe["partes"], list)
    assert isinstance(pe["partes_privadas"], list)
    assert isinstance(pe["partes_publicas"], list)


# ── extract_partes: basic ──────────────────────────────────────────────────────

def test_empty_text():
    assert extract_partes("") == []


def test_no_labels():
    assert extract_partes("This is a regular text without any party labels.") == []


def test_single_contratada_ltda():
    text = (
        "Contratada: CONSTRUMEDICI Engenharia e Comércio Ltda.\n"
        "Objeto: Construção de escola"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    p = partes[0]
    assert "CONSTRUMEDICI" in p["nome_raw"]
    assert p["tipo_parte"] == "PRIVADA"
    assert p["papel"] == "CONTRATADA"
    assert p["confidence"] == "high"


def test_contratante_prefeitura():
    text = (
        "Contratante: Prefeitura Municipal de Holambra.\n"
        "Contratada: Jofege Pavimentação e Construção Ltda.\n"
        "Objeto: Pavimentação"
    )
    partes = extract_partes(text)
    assert len(partes) == 2
    contratante = [p for p in partes if p["papel"] == "CONTRATANTE"][0]
    assert contratante["tipo_parte"] == "PUBLICA"
    assert contratante["confidence"] == "high"
    contratada = [p for p in partes if p["papel"] == "CONTRATADA"][0]
    assert contratada["tipo_parte"] == "PRIVADA"
    assert contratada["confidence"] == "high"


def test_responsavel_is_pf():
    text = (
        "Responsável(is): David Everson Uip (Secretário Estadual)\n"
        "Objeto: Convênio"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    p = partes[0]
    assert p["tipo_parte"] == "PF"
    assert p["confidence"] == "high"
    assert p["cargo"] == "Secretário Estadual"


def test_advogado_oab_stripped():
    """OAB patterns must be stripped from advogado nome_raw (req E)."""
    text = (
        "Advogado(s): Maria José da Silva (OAB/SP nº 123.456)\n"
        "Objeto: Recurso"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    p = partes[0]
    assert p["tipo_parte"] == "PF"
    assert p["papel"] == "ADVOGADO"
    assert "OAB" not in p["nome_raw"]
    assert "123.456" not in p["nome_raw"]


def test_fundacao_classified_as_public():
    """Fundação without 'Pública' → PUBLICA medium."""
    text = (
        "Contratante: Fundação Butantan.\n"
        "Objeto: Aquisição de insumos"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PUBLICA"
    assert p["confidence"] in ("high", "medium")


def test_convenente_conveniada():
    text = (
        "Convenente: Secretaria de Estado da Saúde.\n"
        "Conveniada: Hospital das Clínicas - FAMESP.\n"
        "Objeto: Gestão hospitalar"
    )
    partes = extract_partes(text)
    assert len(partes) == 2
    conv = [p for p in partes if p["papel"] == "CONVENENTE"][0]
    assert conv["tipo_parte"] == "PUBLICA"
    assert conv["confidence"] == "high"


def test_recorrente_ex_prefeito():
    text = (
        "Recorrente: Marcelo Fortes Barbieri – Ex-Prefeito do "
        "Município de Araraquara.\n"
        "EMENTA"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    assert partes[0]["tipo_parte"] == "PF"
    assert partes[0]["papel"] == "RECORRENTE"


def test_multiple_tc_headers():
    text = (
        "TC-001.234.56-7\n"
        "Contratante: Prefeitura Municipal de Campinas.\n"
        "Contratada: ABC Construtora Ltda.\n"
        "Objeto: Obra\n\n"
        "TC-002.345.67-8\n"
        "Contratante: Câmara Municipal de Santos.\n"
        "Contratada: XYZ Serviços S/A.\n"
        "Objeto: Manutenção\n\n"
        "EMENTA"
    )
    partes = extract_partes(text)
    assert len(partes) >= 4
    nomes = [p["nome_raw"] for p in partes]
    assert any("Campinas" in n for n in nomes)
    assert any("Santos" in n for n in nomes)


def test_encoding_replacement_chars():
    """Even with replacement chars, LTDA suffix classifies as PRIVADA."""
    text = (
        "Contratada: Nascente Refei\ufffdoes Coletivas Ltda.\n"
        "Objeto: Fornecimento"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    assert partes[0]["tipo_parte"] == "PRIVADA"


# ── Ambiguous entities (req F) ────────────────────────────────────────────────

def test_companhia_do_estado_is_publica():
    """Companhia de Saneamento do Estado → PUBLICA wins over any PRIVADA keyword."""
    text = (
        "Contratante: Companhia de Saneamento do Estado de São Paulo - SABESP.\n"
        "Objeto: Obra de saneamento"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PUBLICA"
    assert p["confidence"] == "high"


def test_fundacao_instituto_is_publica():
    """Instituto Tecnológico (no 'Federal') → PUBLICA medium."""
    text = (
        "Contratante: Fundação Instituto Tecnológico de Osasco – FITO.\n"
        "Objeto: Construção"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PUBLICA"
    assert p["confidence"] in ("high", "medium")


def test_secretaria_is_publica():
    text = (
        "Convenente: Secretaria de Estado da Saúde – CGOF.\n"
        "Objeto: Convênio"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PUBLICA"
    assert p["confidence"] == "high"


# ── Conservative " e " split (req C) ──────────────────────────────────────────

def test_e_not_split_in_company_name():
    """'Engenharia e Comércio Ltda' must NOT be split — both sides together form one entity."""
    text = (
        "Contratada: CONSTRUMEDICI Engenharia e Comércio Ltda.\n"
        "Objeto: Obra"
    )
    partes = extract_partes(text)
    # Should be exactly 1 party, not 2
    contratadas = [p for p in partes if p["papel"] == "CONTRATADA"]
    assert len(contratadas) == 1
    assert "CONSTRUMEDICI" in contratadas[0]["nome_raw"]


def test_e_split_between_two_entities():
    """Two separate people with ' e ' between them should be split."""
    text = (
        "Responsáveis: José Carlos Pedroso (Presidente da FITO) e "
        "Reginaldo Mariano da Silva (Presidente da Comissão de Fiscalização).\n"
        "Objeto: Licitação"
    )
    partes = extract_partes(text)
    responsaveis = [p for p in partes if p["papel"] == "RESPONSAVEL"]
    assert len(responsaveis) == 2


# ── Header window limit (req B) ──────────────────────────────────────────────

def test_labels_after_ementa_ignored():
    """Labels appearing after EMENTA in text should not be extracted."""
    text = (
        "Contratante: Prefeitura Municipal de X.\n"
        "Objeto: Obra\n"
        "EMENTA: Licitação.\n"
        "Contratada: Empresa Fantasma Ltda.\n"
        "ACORDAM."
    )
    partes = extract_partes(text)
    # Only the Contratante should appear (before EMENTA)
    assert len(partes) == 1
    assert partes[0]["papel"] == "CONTRATANTE"


# ── CNPJ extraction (req E) ──────────────────────────────────────────────────

def test_cnpj_extracted_and_stripped():
    text = (
        "Contratada: Empresa XYZ Ltda. - CNPJ: 12.345.678/0001-99.\n"
        "Objeto: Fornecimento"
    )
    partes = extract_partes(text)
    assert len(partes) >= 1
    p = partes[0]
    assert p["cnpj_cpf"] == "12.345.678/0001-99"
    assert "12.345.678" not in p["nome_raw"]


# ── Contratante default LOW when no keywords (req D) ─────────────────────────

def test_contratante_unknown_entity_is_publica_low():
    """Contratante with unrecognized entity → PUBLICA but LOW confidence."""
    text = (
        "Contratante: Associação dos Moradores do Bairro.\n"
        "Objeto: Convênio"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PUBLICA"
    assert p["confidence"] == "low"


def test_contratada_unknown_entity_is_privada_low():
    """Contratada with unrecognized entity → PRIVADA but LOW confidence."""
    text = (
        "Contratada: Alpha Beta Gama Comissão Organizadora.\n"
        "Objeto: Evento"
    )
    partes = extract_partes(text)
    p = partes[0]
    assert p["tipo_parte"] == "PRIVADA"
    assert p["confidence"] == "low"


# ── parse_text integration ────────────────────────────────────────────────────

def test_parse_text_with_parties():
    text = (
        "TRIBUNAL DE CONTAS DO ESTADO DE SÃO PAULO\n"
        "PROCESSO TC-010026.989.24-4\n"
        "Contratante: Prefeitura Municipal de Holambra.\n"
        "Contratada: Engeko Engenharia e Construção Ltda.\n"
        "Objeto: Obra de pavimentação.\n"
        "EMENTA: Licitação irregular.\n"
        "ACORDAM em julgar irregular."
    )
    result = parse_text(text)
    pe = result["party_extraction"]
    assert len(pe["partes_privadas"]) >= 1
    assert len(pe["partes_publicas"]) >= 1
    assert pe["version"] == 1


def test_parse_text_no_parties():
    text = "TRIBUNAL DE CONTAS\nEMENTA: Consulta.\nACORDAM em responder a consulta."
    result = parse_text(text)
    pe = result["party_extraction"]
    assert pe["partes"] == []
    assert pe["partes_privadas"] == []
    assert pe["partes_publicas"] == []
