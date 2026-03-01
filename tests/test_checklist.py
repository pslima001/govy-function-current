"""
Tests for govy.checklist — Issue C: MVP gerador de checklist
=============================================================
Unit tests (no network). Integration tests require AZURE_SEARCH_API_KEY.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.checklist.audit_questions import (
    AUDIT_QUESTIONS,
    AuditQuestion,
    get_questions_by_stage,
    get_all_stage_tags,
)
from govy.checklist.models import (
    CheckItem,
    ChecklistResult,
    GuiaTcuRef,
    SINALIZACAO_OK,
    SINALIZACAO_ATENCAO,
    SINALIZACAO_NAO_CONFORME,
    SINALIZACAO_NAO_IDENTIFICADO,
    SINALIZACOES_VALIDAS,
)
from govy.checklist.generator import (
    generate_checklist,
    _normalize_text,
    _find_keyword_snippet,
    _classify_sinalizacao,
)


# ─── Audit Questions Unit Tests ───────────────────────────────────────────────

class TestAuditQuestions:
    def test_minimum_questions(self):
        """Must have at least 10 questions."""
        assert len(AUDIT_QUESTIONS) >= 10

    def test_unique_ids(self):
        """All question IDs must be unique."""
        ids = [q.id for q in AUDIT_QUESTIONS]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_all_have_keywords(self):
        """Every question must have at least one keyword."""
        for q in AUDIT_QUESTIONS:
            assert len(q.keywords_edital) > 0, f"{q.id} has no keywords"

    def test_all_have_query_guia_tcu(self):
        """Every question must have a query for the retriever."""
        for q in AUDIT_QUESTIONS:
            assert q.query_guia_tcu.strip(), f"{q.id} has empty query_guia_tcu"

    def test_valid_stage_tags(self):
        """All stage_tags must be from the frozen enum."""
        valid = {"planejamento", "edital", "seleção", "contrato", "gestão", "governança"}
        for q in AUDIT_QUESTIONS:
            assert q.stage_tag in valid, f"{q.id} has invalid stage_tag: {q.stage_tag}"

    def test_valid_severidade(self):
        """Severidade must be alta, media, or baixa."""
        valid = {"alta", "media", "baixa"}
        for q in AUDIT_QUESTIONS:
            assert q.severidade in valid, f"{q.id} has invalid severidade: {q.severidade}"

    def test_stage_coverage(self):
        """Must cover at least 3 distinct stage_tags."""
        stages = set(q.stage_tag for q in AUDIT_QUESTIONS)
        assert len(stages) >= 3, f"Only {len(stages)} stages covered: {stages}"

    def test_get_questions_by_stage(self):
        qs = get_questions_by_stage("edital")
        assert len(qs) > 0
        assert all(q.stage_tag == "edital" for q in qs)

    def test_get_all_stage_tags(self):
        tags = get_all_stage_tags()
        assert len(tags) >= 3
        assert "edital" in tags


# ─── Models Unit Tests ─────────────────────────────────────────────────────────

class TestModels:
    def test_sinalizacoes_validas(self):
        assert SINALIZACAO_OK in SINALIZACOES_VALIDAS
        assert SINALIZACAO_ATENCAO in SINALIZACOES_VALIDAS
        assert SINALIZACAO_NAO_CONFORME in SINALIZACOES_VALIDAS
        assert SINALIZACAO_NAO_IDENTIFICADO in SINALIZACOES_VALIDAS

    def test_check_item_to_dict(self):
        ref = GuiaTcuRef("S1", "Title", "http://example.com", 0.95)
        item = CheckItem(
            check_id="PL-001",
            stage_tag="planejamento",
            pergunta_de_auditoria="Pergunta?",
            sinalizacao=SINALIZACAO_OK,
            trecho_do_edital="trecho...",
            referencia_guia_tcu=ref,
            observacao="obs",
        )
        d = item.to_dict()
        assert d["check_id"] == "PL-001"
        assert d["sinalizacao"] == "OK"
        assert d["referencia_guia_tcu"]["section_id"] == "S1"

    def test_checklist_result_to_dict(self):
        result = ChecklistResult(
            run_id="abc123",
            arquivo_analisado="test.pdf",
            total_checks=0,
        )
        d = result.to_dict()
        assert d["kind"] == "checklist_edital_v1"
        assert d["run_id"] == "abc123"
        assert d["checks"] == []


# ─── Generator Unit Tests ──────────────────────────────────────────────────────

# Fake edital text with known keywords
FAKE_EDITAL = """
PREGÃO ELETRÔNICO Nº 001/2025
EDITAL DE LICITAÇÃO

1. DO OBJETO
A presente licitação tem por objeto a contratação de serviços de tecnologia.
O Estudo Técnico Preliminar (ETP) encontra-se anexo ao processo.
O Termo de Referência detalha as especificações.

2. DA PESQUISA DE PREÇOS
A estimativa de valor foi elaborada com base em pesquisa de mercado,
conforme preço de referência obtido junto ao Painel de Preços.
Dotação orçamentária: 12.345.678.9012.

3. DA HABILITAÇÃO
3.1 Habilitação Jurídica: ato constitutivo, estatuto ou contrato social.
3.2 Habilitação Técnica: atestado de capacidade técnica.
3.3 Qualificação Econômico-Financeira: balanço patrimonial.

4. DO JULGAMENTO
Critério de julgamento: menor preço.
Modo de disputa: aberto.

5. DOS RECURSOS
Prazo recursal conforme Lei 14.133/2021.
Impugnação ao edital poderá ser feita até 3 dias úteis.

6. DO CONTRATO
Minuta do contrato em anexo.
Vigência: 12 meses, prorrogável.
Garantia contratual de 5%.

7. DA FISCALIZAÇÃO
Fiscal do contrato será designado pela área requisitante.
Pagamento mediante nota fiscal atestada.

8. DISPOSIÇÕES FINAIS
Publicação no Diário Oficial e no PNCP.
Tratamento diferenciado para ME/EPP conforme LC 123.
"""


class TestNormalizeText:
    def test_lowercase(self):
        assert "abc" in _normalize_text("ABC")

    def test_collapse_whitespace(self):
        result = _normalize_text("a   b\n\nc")
        assert "a b c" == result


class TestFindKeywordSnippet:
    def test_finds_keyword(self):
        text = FAKE_EDITAL
        text_lower = _normalize_text(text)
        snippet = _find_keyword_snippet(text_lower, text, ["estudo técnico preliminar"])
        assert snippet is not None
        assert "ETP" in snippet or "estudo" in snippet.lower()

    def test_returns_none_when_not_found(self):
        text = FAKE_EDITAL
        text_lower = _normalize_text(text)
        snippet = _find_keyword_snippet(text_lower, text, ["xyznonexistent"])
        assert snippet is None

    def test_snippet_has_context(self):
        text = FAKE_EDITAL
        text_lower = _normalize_text(text)
        snippet = _find_keyword_snippet(text_lower, text, ["habilitação jurídica"])
        assert snippet is not None
        assert len(snippet) > len("habilitação jurídica")


class TestClassifySinalizacao:
    def test_keyword_found_is_ok(self):
        assert _classify_sinalizacao(True, [], "") == SINALIZACAO_OK

    def test_keyword_not_found_no_ausencia(self):
        assert _classify_sinalizacao(False, [], "") == SINALIZACAO_NAO_IDENTIFICADO

    def test_keyword_not_found_ausencia_present(self):
        result = _classify_sinalizacao(False, ["proibido"], "texto proibido aqui")
        assert result == SINALIZACAO_NAO_CONFORME

    def test_keyword_not_found_ausencia_absent(self):
        result = _classify_sinalizacao(False, ["proibido"], "texto limpo aqui")
        assert result == SINALIZACAO_NAO_IDENTIFICADO


class TestGenerateChecklist:
    def test_generates_with_fake_edital(self):
        """Core test: generate checklist without retriever."""
        result = generate_checklist(
            FAKE_EDITAL,
            arquivo_nome="fake_edital.pdf",
            use_retriever=False,
        )
        assert isinstance(result, ChecklistResult)
        assert result.total_checks == len(AUDIT_QUESTIONS)
        assert result.arquivo_analisado == "fake_edital.pdf"

    def test_has_ok_checks(self):
        """Fake edital has many keywords, so some checks should be OK."""
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        ok_count = result.sinalizacao_distribution.get(SINALIZACAO_OK, 0)
        assert ok_count > 0, f"Expected some OK checks, got: {result.sinalizacao_distribution}"

    def test_covers_multiple_stages(self):
        """Result should cover at least 3 stage_tags."""
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        assert len(result.stage_tag_distribution) >= 3

    def test_output_json_valid(self):
        """to_dict() must produce valid structure."""
        import json
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["kind"] == "checklist_edital_v1"
        assert len(parsed["checks"]) == result.total_checks

    def test_all_sinalizacoes_valid(self):
        """Every check must have a valid sinalizacao."""
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        for c in result.checks:
            assert c.sinalizacao in SINALIZACOES_VALIDAS, (
                f"{c.check_id} has invalid sinalizacao: {c.sinalizacao}"
            )

    def test_run_id_present(self):
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        assert result.run_id and len(result.run_id) == 8

    def test_short_text_rejected(self):
        with pytest.raises(ValueError, match="muito curto"):
            generate_checklist("abc", use_retriever=False)

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            generate_checklist("", use_retriever=False)

    def test_snippet_present_when_ok(self):
        """OK checks should have a trecho_do_edital."""
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        ok_checks = [c for c in result.checks if c.sinalizacao == SINALIZACAO_OK]
        for c in ok_checks:
            assert c.trecho_do_edital, f"{c.check_id} is OK but has no snippet"

    def test_specific_checks_found(self):
        """Verify specific keywords are found in the fake edital."""
        result = generate_checklist(FAKE_EDITAL, use_retriever=False)
        check_map = {c.check_id: c for c in result.checks}

        # ETP is mentioned
        assert check_map["PL-001"].sinalizacao == SINALIZACAO_OK
        # Termo de referência is mentioned
        assert check_map["PL-002"].sinalizacao == SINALIZACAO_OK
        # Critério de julgamento is mentioned
        assert check_map["ED-003"].sinalizacao == SINALIZACAO_OK
        # Lei 14.133 is mentioned
        assert check_map["GO-001"].sinalizacao == SINALIZACAO_OK


# ─── Integration tests (requires retriever) ──────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("AZURE_SEARCH_API_KEY"),
    reason="AZURE_SEARCH_API_KEY not set (integration test)",
)
class TestChecklistWithRetriever:
    def test_generates_with_retriever(self):
        result = generate_checklist(FAKE_EDITAL, use_retriever=True)
        assert result.total_checks == len(AUDIT_QUESTIONS)
        # With retriever, OK checks should have guia_tcu references
        ok_checks = [c for c in result.checks if c.sinalizacao == SINALIZACAO_OK]
        refs_found = sum(1 for c in ok_checks if c.referencia_guia_tcu.section_title)
        assert refs_found > 0, "Expected at least 1 guia_tcu reference"
