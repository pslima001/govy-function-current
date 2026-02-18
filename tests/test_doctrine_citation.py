"""Tests for govy.doctrine.citation_extractor — citation metadata extraction."""

from __future__ import annotations

from govy.doctrine.citation_extractor import extract_citation_meta


class TestExtractCitationMeta:
    def test_empty_string(self):
        assert extract_citation_meta("") == {}

    def test_tcu_detected(self):
        result = extract_citation_meta("Acórdão do TCU sobre licitação")
        assert result["tribunal"] == "TCU"

    def test_stj_detected(self):
        result = extract_citation_meta("Decisão do STJ em recurso especial")
        assert result["tribunal"] == "STJ"

    def test_stf_detected(self):
        result = extract_citation_meta("Julgamento do STF sobre constitucionalidade")
        assert result["tribunal"] == "STF"

    def test_tj_state_detected(self):
        result = extract_citation_meta("Decisão do TJSP sobre contrato administrativo")
        assert result["tribunal"] == "TJSP"

    def test_acordao_with_number(self):
        result = extract_citation_meta("Acórdão no 1234/2023 do TCU")
        assert result["tipo_decisao"] == "Acórdão"
        assert result["numero"] == "1234/2023"

    def test_ementa_tipo_decisao(self):
        result = extract_citation_meta("EMENTA: O princípio da legalidade")
        assert result["tipo_decisao"] == "Ementa"

    def test_voto_tipo_decisao(self):
        result = extract_citation_meta("VOTO do relator sobre a matéria")
        assert result["tipo_decisao"] == "Voto"

    def test_processo_number(self):
        result = extract_citation_meta("Processo no 12345/2023 do TCU")
        assert result["processo"] == "12345/2023"

    def test_orgao_julgador_plenario(self):
        result = extract_citation_meta("O Plenário decidiu que")
        assert result["orgao_julgador"] is not None
        assert "plenário" in result["orgao_julgador"].lower() or "Plenário" in result["orgao_julgador"]

    def test_relator(self):
        result = extract_citation_meta("Relator: Ministro João Silva")
        assert result["relator"] is not None
        assert "Ministro João Silva" in result["relator"]

    def test_date_extraction(self):
        result = extract_citation_meta("Julgado em 15/03/2023 pelo STJ")
        assert result["data"] == "15/03/2023"

    def test_trecho_rotulo_ementa(self):
        result = extract_citation_meta("A ementa dispõe que a licitação")
        assert result["trecho_rotulo"] == "Ementa"

    def test_trecho_rotulo_voto(self):
        result = extract_citation_meta("No voto, o relator afirmou")
        assert result["trecho_rotulo"] == "Voto"

    def test_no_matches_returns_all_none(self):
        result = extract_citation_meta("Texto puro de doutrina sem referências judiciais")
        assert result["tribunal"] is None
        assert result["tipo_decisao"] is None
        assert result["numero"] is None

    def test_full_citation(self):
        text = "TCU, Acórdão no 999/2022, Plenário, Relator: Min. Carlos, 10/05/2022"
        result = extract_citation_meta(text)
        assert result["tribunal"] == "TCU"
        assert result["tipo_decisao"] == "Acórdão"
        assert result["numero"] == "999/2022"
        assert result["relator"] is not None
        assert result["data"] == "10/05/2022"
