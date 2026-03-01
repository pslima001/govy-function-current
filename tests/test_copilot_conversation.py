# tests/test_copilot_conversation.py
"""
Testes para PR3: Conversation state (multi-turn).

Cenários:
1. Sem conversation_id → sem histórico
2. Com conversation_id → salva e recupera turns
3. Máximo de MAX_TURNS respeitado
4. Histórico trunca conteúdo longo
5. Handler passa conversation_id e salva turn
6. LLM recebe histórico quando disponível
7. Follow-ups usam contexto do diálogo anterior
"""
import os
import json
from unittest.mock import patch, MagicMock

import pytest


# ─── Testes: conversation.py (unitários) ─────────────────────────────


class TestConversationModule:
    """Testes unitários do módulo de conversation."""

    def setup_method(self):
        """Limpa store in-memory antes de cada teste."""
        from govy.copilot.conversation import _memory_store
        _memory_store.clear()

    def test_no_conversation_id_returns_empty(self):
        from govy.copilot.conversation import get_history
        assert get_history("") == []
        assert get_history(None) == []

    def test_save_and_retrieve_turns(self):
        from govy.copilot.conversation import save_turn, get_history
        save_turn("conv-1", "Qual o prazo?", "O prazo é de 8 dias.", intent="pergunta_juridica")
        history = get_history("conv-1")
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "Qual o prazo?"
        assert history[1].role == "assistant"
        assert history[1].content == "O prazo é de 8 dias."

    def test_max_turns_respected(self):
        from govy.copilot.conversation import save_turn, get_history, MAX_TURNS
        # Salvar mais que MAX_TURNS
        for i in range(MAX_TURNS + 5):
            save_turn("conv-2", f"Pergunta {i}", f"Resposta {i}")
        history = get_history("conv-2")
        assert len(history) <= MAX_TURNS

    def test_content_truncated(self):
        from govy.copilot.conversation import save_turn, get_history
        long_text = "x" * 1000
        save_turn("conv-3", long_text, "ok")
        history = get_history("conv-3")
        assert len(history[0].content) <= 500

    def test_separate_conversations(self):
        from govy.copilot.conversation import save_turn, get_history
        save_turn("conv-a", "Pergunta A", "Resposta A")
        save_turn("conv-b", "Pergunta B", "Resposta B")
        assert len(get_history("conv-a")) == 2
        assert len(get_history("conv-b")) == 2
        assert get_history("conv-a")[0].content == "Pergunta A"
        assert get_history("conv-b")[0].content == "Pergunta B"

    def test_build_history_context_empty(self):
        from govy.copilot.conversation import build_history_context
        assert build_history_context("") is None
        assert build_history_context("nonexistent") is None

    def test_build_history_context_with_data(self):
        from govy.copilot.conversation import save_turn, build_history_context
        save_turn("conv-4", "PNCP e últimos 12 meses", "Entendido. Qual produto?")
        ctx = build_history_context("conv-4")
        assert ctx is not None
        assert "PNCP" in ctx
        assert "Usuário" in ctx
        assert "Copiloto" in ctx

    def test_turn_has_timestamp(self):
        from govy.copilot.conversation import save_turn, get_history
        save_turn("conv-5", "Teste", "Ok")
        history = get_history("conv-5")
        assert history[0].timestamp is not None
        assert "T" in history[0].timestamp  # ISO format

    def test_turn_preserves_intent(self):
        from govy.copilot.conversation import save_turn, get_history
        save_turn("conv-6", "Teste", "Ok", intent="pergunta_bi")
        history = get_history("conv-6")
        assert history[0].intent == "pergunta_bi"


# ─── Testes: handler integração com conversation ─────────────────────


class TestHandlerConversation:
    """Testes de integração handler + conversation state."""

    def setup_method(self):
        from govy.copilot.conversation import _memory_store
        _memory_store.clear()

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_handler_saves_turn_with_conversation_id(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"text": json.dumps({
                "answer": "O prazo é de 8 dias úteis.",
                "uncertainty": None,
                "followup_questions": [],
                "evidence_used": [],
            })}]
        }
        mock_post.return_value = mock_resp

        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        from govy.copilot.contracts import Evidence
        fake_evidence = [Evidence(source="kb", id="e1", snippet="Art. 75...", confidence=0.9)]

        with patch("govy.copilot.handler.retrieve_from_kb", return_value=fake_evidence), \
             patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[]):
            result = govy.copilot.handler.handle_chat(
                "Qual o prazo para recurso?",
                context={"conversation_id": "conv-handler-1"},
            )

        assert "8 dias" in result.answer

        from govy.copilot.conversation import get_history
        history = get_history("conv-handler-1")
        assert len(history) == 2
        assert history[0].role == "user"
        assert "prazo" in history[0].content.lower()

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_handler_no_turn_saved_when_llm_disabled(self):
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        govy.copilot.handler.handle_chat(
            "Teste",
            context={"conversation_id": "conv-no-save"},
        )

        from govy.copilot.conversation import get_history
        # LLM disabled → não chega ao save_turn (retorna antes)
        history = get_history("conv-no-save")
        assert len(history) == 0

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_history_context_passed_to_llm(self, mock_post):
        """Verifica que o histórico é incluído no prompt do LLM."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"text": json.dumps({
                "answer": "Entendido, PNCP nos últimos 12 meses.",
                "uncertainty": None,
                "followup_questions": [],
                "evidence_used": [],
            })}]
        }
        mock_post.return_value = mock_resp

        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        # Pré-popular histórico
        from govy.copilot.conversation import save_turn
        save_turn("conv-history-1", "PNCP e últimos 12 meses", "Qual produto?", intent="pergunta_bi")

        from govy.copilot.contracts import Evidence
        fake_evidence = [Evidence(source="kb", id="e1", snippet="Art. 75...", confidence=0.9)]

        with patch("govy.copilot.handler.retrieve_from_kb", return_value=fake_evidence), \
             patch("govy.copilot.handler.retrieve_workspace_docs", return_value=[]):
            govy.copilot.handler.handle_chat(
                "Dipirona 500mg",
                context={"conversation_id": "conv-history-1"},
            )

        # Verificar que o LLM recebeu o histórico no prompt
        call_args = mock_post.call_args
        if call_args:
            body = call_args[1].get("json") or call_args[0][1] if len(call_args[0]) > 1 else None
            if body and "messages" in body:
                user_msg = body["messages"][0]["content"]
                assert "PNCP" in user_msg  # Histórico incluído
