# tests/test_copilot_steps2_3_4.py
"""
Testes dos Steps #1-#4 do Copiloto:
  #1 Context Router + WorkspaceContext
  #2 Defense Guardrail
  #3 Retrieval Guard
  #4 Explain Checklist
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ["BI_ENABLED"] = "false"

from govy.copilot.router import (
    detect_intent,
    detect_context,
    build_workspace_context,
)
from govy.copilot.contracts import CopilotOutput, WorkspaceContext


# ==============================================================================
# Step #1: Context Router + WorkspaceContext
# ==============================================================================

class TestDetectContext(unittest.TestCase):

    def test_site_geral_empty_context(self):
        self.assertEqual(detect_context({}), "site_geral")

    def test_site_geral_no_workspace(self):
        self.assertEqual(detect_context({"uf": "SP"}), "site_geral")

    def test_workspace_with_workspace_id(self):
        self.assertEqual(detect_context({"workspace_id": "ws-1"}), "licitacao_workspace")

    def test_workspace_with_licitacao_id(self):
        self.assertEqual(detect_context({"licitacao_id": "lic-1"}), "licitacao_workspace")


class TestBuildWorkspaceContext(unittest.TestCase):

    def test_site_geral(self):
        ws = build_workspace_context({})
        self.assertEqual(ws.mode, "site_geral")
        self.assertIsNone(ws.workspace_id)
        self.assertEqual(ws.available_docs, [])
        self.assertFalse(ws.has_indexed_text)

    def test_workspace_basic(self):
        ws = build_workspace_context({
            "workspace_id": "ws-123",
            "licitacao_id": "lic-456",
            "uf": "PR",
            "orgao": "Prefeitura de Curitiba",
        })
        self.assertEqual(ws.mode, "licitacao_workspace")
        self.assertEqual(ws.workspace_id, "ws-123")
        self.assertEqual(ws.licitacao_id, "lic-456")
        self.assertEqual(ws.uf, "PR")
        self.assertEqual(ws.orgao, "Prefeitura de Curitiba")

    def test_workspace_with_docs(self):
        ws = build_workspace_context({
            "workspace_id": "ws-1",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
                {"name": "TR_v2.pdf", "doc_type": "tr", "indexed": True},
                {"name": "minuta.pdf", "doc_type": "minuta", "indexed": False},
            ],
        })
        self.assertEqual(len(ws.available_docs), 3)
        self.assertTrue(ws.has_indexed_text)
        self.assertTrue(ws.has_doc_type("edital"))
        self.assertTrue(ws.has_doc_type("tr"))
        self.assertFalse(ws.has_doc_type("etp"))
        self.assertEqual(ws.doc_names(), ["edital.pdf", "TR_v2.pdf", "minuta.pdf"])

    def test_workspace_docs_not_indexed(self):
        ws = build_workspace_context({
            "workspace_id": "ws-1",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": False},
            ],
        })
        self.assertFalse(ws.has_indexed_text)
        self.assertEqual(len(ws.available_docs), 1)

    def test_workspace_empty_docs(self):
        ws = build_workspace_context({
            "workspace_id": "ws-1",
            "available_docs": [],
        })
        self.assertEqual(ws.available_docs, [])
        self.assertFalse(ws.has_indexed_text)

    def test_malformed_docs_ignored(self):
        ws = build_workspace_context({
            "workspace_id": "ws-1",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital"},
                "not_a_dict",
                {"no_name_key": True},
                None,
            ],
        })
        self.assertEqual(len(ws.available_docs), 1)


class TestNoEvidenceWorkspaceAware(unittest.TestCase):
    """
    Testa que a resposta 'sem evidência' muda conforme o contexto do workspace.
    Regra: Se ctx=licitacao_workspace, nunca perguntar 'envie o edital' se já tem docs.
    """

    @patch("govy.copilot.handler.retrieve_from_kb", return_value=[])
    @patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[])
    def test_site_geral_no_evidence_suggests_workspace(self, mock_ws, mock_kb):
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {})
        self.assertIn("needs_more_context", result.flags)
        self.assertEqual(result.flags["workspace_mode"], "site_geral")
        self.assertIn("workspace", result.answer.lower())

    @patch("govy.copilot.handler.retrieve_from_kb", return_value=[])
    @patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[])
    def test_workspace_with_indexed_docs_no_evidence(self, mock_ws, mock_kb):
        """No workspace com docs indexados mas sem resultado — NÃO pede 'envie edital'."""
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {
            "workspace_id": "ws-1",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
            ],
        })
        self.assertIn("needs_more_context", result.flags)
        self.assertTrue(result.flags["has_indexed_text"])
        self.assertIn("edital.pdf", result.answer)
        self.assertNotIn("envie o edital", result.answer.lower())
        self.assertNotIn("anexe", result.answer.lower())

    @patch("govy.copilot.handler.retrieve_from_kb", return_value=[])
    @patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[])
    def test_workspace_with_unindexed_docs(self, mock_ws, mock_kb):
        """Workspace com docs NÃO indexados — sugere colar trecho."""
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {
            "workspace_id": "ws-1",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": False},
            ],
        })
        self.assertIn("needs_more_context", result.flags)
        self.assertFalse(result.flags["has_indexed_text"])
        self.assertIn("não foram indexados", result.answer.lower())

    @patch("govy.copilot.handler.retrieve_from_kb", return_value=[])
    @patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[])
    def test_workspace_no_docs(self, mock_ws, mock_kb):
        """Workspace sem docs — pede para anexar."""
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {
            "workspace_id": "ws-1",
            "available_docs": [],
        })
        self.assertIn("needs_more_context", result.flags)
        self.assertIn("não tem documentos", result.answer.lower())


# ==============================================================================
# Step #2: Defense Guardrail
# ==============================================================================

class TestDefenseGuardrail(unittest.TestCase):
    """Garante que frases de defesa são SEMPRE bloqueadas."""

    DEFENSE_PHRASES = [
        # Diretos
        "elabore um recurso administrativo",
        "faça uma impugnação",
        "prepare contrarrazões para mim",
        "redija uma petição administrativa",
        # Ambíguos
        "como recorrer dessa decisão?",
        "quero impugnar o edital",
        "preciso contestar esse resultado",
        "posso recorrer dessa habilitação?",
        "me ajude a recorrer",
        "me ajuda com a defesa",
        # Pedidos de modelo/template
        "modelo de recurso administrativo",
        "template de impugnação",
        "minuta de defesa administrativa",
        # Verbos de produção
        "crie um recurso para mim",
        "gere uma peça de defesa",
        "monte uma impugnação ao edital",
        "escreva uma petição",
        "produza contrarrazões",
        # Com contexto
        "preciso de uma defesa administrativa contra a inabilitação",
        "faça a manifestação prévia de defesa",
        "elabore as razões recursais",
    ]

    def test_all_defense_phrases_blocked(self):
        for phrase in self.DEFENSE_PHRASES:
            intent = detect_intent(phrase)
            self.assertEqual(
                intent, "tentativa_defesa",
                f"Frase NÃO bloqueada: '{phrase}' → detectada como '{intent}'"
            )

    NOT_DEFENSE_PHRASES = [
        "quais são os recursos humanos necessários?",
        "recurso financeiro disponível",
        "recurso computacional necessário",
        "recurso material da empresa",
        "o edital exige capacidade técnica?",
        "posso exigir atestado de capacidade?",
        "qual o prazo para entrega?",
    ]

    def test_non_defense_phrases_not_blocked(self):
        for phrase in self.NOT_DEFENSE_PHRASES:
            intent = detect_intent(phrase)
            self.assertNotEqual(
                intent, "tentativa_defesa",
                f"Falso positivo: '{phrase}' detectada como defesa"
            )

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_defense_returns_blocked_flag(self, mock_container):
        from govy.copilot.handler import handle_chat
        result = handle_chat("elabore um recurso administrativo", {})
        self.assertEqual(result.intent, "tentativa_defesa")
        self.assertTrue(result.flags.get("blocked_defense"))
        self.assertIn("Criação de Documentos", result.answer)


# ==============================================================================
# Step #3: Retrieval Guard
# ==============================================================================

class TestRetrievalGuard(unittest.TestCase):

    def test_blocked_doc_types(self):
        from govy.copilot.retrieval import _is_blocked_doc_type
        self.assertTrue(_is_blocked_doc_type("doutrina"))
        self.assertTrue(_is_blocked_doc_type("Doutrina"))
        self.assertTrue(_is_blocked_doc_type("DOUTRINA"))
        self.assertTrue(_is_blocked_doc_type("opinião"))
        self.assertTrue(_is_blocked_doc_type("opiniao"))
        self.assertTrue(_is_blocked_doc_type("artigo_externo"))
        self.assertFalse(_is_blocked_doc_type("lei"))
        self.assertFalse(_is_blocked_doc_type("jurisprudencia"))
        self.assertFalse(_is_blocked_doc_type("guia_tcu"))
        self.assertFalse(_is_blocked_doc_type(""))
        self.assertFalse(_is_blocked_doc_type(None))

    def test_doc_to_evidence_extracts_snippet(self):
        from govy.copilot.retrieval import _doc_to_evidence
        ev = _doc_to_evidence({
            "chunk_id": "c1",
            "content": "Este é o conteúdo de teste",
            "semantic_score": 3.5,
            "doc_type": "lei",
        })
        self.assertEqual(ev.source, "kb")
        self.assertEqual(ev.id, "c1")
        self.assertEqual(ev.snippet, "Este é o conteúdo de teste")
        self.assertAlmostEqual(ev.confidence, 3.5 / 4.0, places=2)

    def test_doc_to_evidence_fallback_text_field(self):
        """Se content e snippet estão vazios, tenta text field."""
        from govy.copilot.retrieval import _doc_to_evidence
        ev = _doc_to_evidence({
            "id": "c2",
            "content": "",
            "snippet": "",
            "text": "Fallback text content",
            "search_score": 2.0,
        })
        self.assertEqual(ev.snippet, "Fallback text content")

    def test_min_confidence_filter(self):
        from govy.copilot.retrieval import MIN_CONFIDENCE
        self.assertGreater(MIN_CONFIDENCE, 0)
        self.assertLessEqual(MIN_CONFIDENCE, 0.5)


# ==============================================================================
# Step #4: Explain Checklist
# ==============================================================================

class TestExplainChecklist(unittest.TestCase):

    def test_checklist_lookup_valid_id(self):
        from govy.copilot._checklist_lookup import get_audit_question_by_id
        q = get_audit_question_by_id("PL-001")
        self.assertIsNotNone(q, "PL-001 deve existir no audit_questions")
        self.assertEqual(q["id"], "PL-001")
        self.assertEqual(q["stage_tag"], "planejamento")
        self.assertIn("pergunta", q)
        self.assertIn("keywords_edital", q)
        self.assertIn("severidade", q)

    def test_checklist_lookup_invalid_id(self):
        from govy.copilot._checklist_lookup import get_audit_question_by_id
        q = get_audit_question_by_id("XX-999")
        self.assertIsNone(q)

    def test_checklist_lookup_all_stages(self):
        from govy.copilot._checklist_lookup import get_audit_question_by_id
        # Verificar que existem IDs de cada estágio
        for prefix in ["PL", "ED", "SE", "CO", "GE", "GO"]:
            q = get_audit_question_by_id(f"{prefix}-001")
            self.assertIsNotNone(q, f"{prefix}-001 deve existir")

    @patch("govy.copilot.handler.retrieve_from_kb", return_value=[])
    @patch("govy.copilot.handler.generate_answer")
    def test_explain_check_known_id(self, mock_llm, mock_kb):
        mock_llm.return_value = {
            "answer": "O item PL-001 verifica se existe estudo técnico preliminar.",
            "uncertainty": None,
            "followup_questions": [],
            "llm_time_ms": 100,
            "llm_model": "test",
        }
        from govy.copilot.handler import explain_check
        result = explain_check("PL-001", "edital-123")
        self.assertEqual(result.intent, "checklist_conformidade")
        self.assertTrue(result.flags["explain_check"])
        self.assertEqual(result.flags["check_id"], "PL-001")
        self.assertTrue(result.flags["found"])
        self.assertIn("PL-001", result.answer)

    def test_explain_check_unknown_id(self):
        from govy.copilot.handler import explain_check
        result = explain_check("XX-999", "edital-123")
        self.assertEqual(result.intent, "checklist_conformidade")
        self.assertFalse(result.flags["found"])
        self.assertIn("XX-999", result.answer)


# ==============================================================================
# Test: workspace_mode flag no output principal
# ==============================================================================

class TestWorkspaceModeInOutput(unittest.TestCase):

    @patch("govy.copilot.handler.retrieve_from_kb")
    @patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[])
    @patch("govy.copilot.handler.generate_answer")
    def test_workspace_mode_in_flags(self, mock_llm, mock_ws, mock_kb):
        from govy.copilot.contracts import Evidence
        mock_kb.return_value = [Evidence(
            source="kb", id="e1", snippet="teste", confidence=0.8
        )]
        mock_llm.return_value = {
            "answer": "Resposta teste",
            "uncertainty": None,
            "followup_questions": [],
            "llm_time_ms": 50,
            "llm_model": "test",
        }
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {"workspace_id": "ws-1"})
        self.assertEqual(result.flags["workspace_mode"], "licitacao_workspace")

    @patch("govy.copilot.handler.retrieve_from_kb")
    @patch("govy.copilot.handler.generate_answer")
    def test_site_geral_mode_in_flags(self, mock_llm, mock_kb):
        from govy.copilot.contracts import Evidence
        mock_kb.return_value = [Evidence(
            source="kb", id="e1", snippet="teste", confidence=0.8
        )]
        mock_llm.return_value = {
            "answer": "Resposta teste",
            "uncertainty": None,
            "followup_questions": [],
            "llm_time_ms": 50,
            "llm_model": "test",
        }
        from govy.copilot.handler import handle_chat
        result = handle_chat("posso exigir atestado?", {})
        self.assertEqual(result.flags["workspace_mode"], "site_geral")


if __name__ == "__main__":
    unittest.main()
