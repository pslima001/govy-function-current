# tests/test_copilot_llm_failclosed.py
"""
Testes para PR1: LLM fail-closed + env vars + logs de auditoria.

Cenários:
1. LLM_ENABLED=false → resposta controlada "IA indisponível"
2. LLM_ENABLED=true sem key → resposta controlada
3. LLM_ENABLED=true com key → responde via LLM
4. Defense block funciona SEM LLM
5. Operacional funciona SEM LLM
6. BI placeholder funciona SEM LLM
7. Audit log contém campos obrigatórios
8. Multi-provider: anthropic e openai
9. explain_check respeita fail-closed
"""
import os
import json
import logging
from unittest.mock import patch, MagicMock

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────

def _reload_handler():
    """Reimporta handler para pegar novas env vars."""
    import importlib
    import govy.copilot.config
    importlib.reload(govy.copilot.config)
    import govy.copilot.llm_answer
    importlib.reload(govy.copilot.llm_answer)
    import govy.copilot.handler
    importlib.reload(govy.copilot.handler)
    return govy.copilot.handler


def _mock_retrieval():
    """Mock das funções de retrieval para não depender de Azure Search."""
    return patch.multiple(
        "govy.copilot.retrieval",
        _get_search_client=MagicMock(return_value=None),
    )


def _mock_kb_with_evidence():
    """Mock do retrieve_from_kb retornando evidência fake."""
    from govy.copilot.contracts import Evidence
    fake_evidence = [
        Evidence(
            source="kb",
            id="test-001",
            snippet="Art. 75, Lei 14.133/2021: dispensa de licitação...",
            confidence=0.85,
            title="Lei 14.133/2021",
            doc_type="lei",
        )
    ]
    return patch("govy.copilot.handler.retrieve_from_kb", return_value=fake_evidence)


def _mock_llm_response():
    """Mock da chamada HTTP ao LLM."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"text": json.dumps({
            "answer": "Resposta de teste do LLM.",
            "uncertainty": None,
            "followup_questions": ["Pergunta 1?"],
            "evidence_used": ["test-001"],
        })}]
    }
    return mock_resp


def _mock_openai_response():
    """Mock da chamada HTTP ao OpenAI."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "answer": "Resposta OpenAI de teste.",
            "uncertainty": None,
            "followup_questions": ["Pergunta OpenAI?"],
            "evidence_used": ["test-001"],
        })}}]
    }
    return mock_resp


# ─── Testes: LLM_ENABLED=false ──────────────────────────────────────


class TestLLMDisabled:
    """Cenários com LLM_ENABLED=false (default)."""

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_chat_returns_ia_indisponivel(self):
        handler = _reload_handler()
        with _mock_retrieval():
            result = handler.handle_chat("Pode exigir certidão negativa?")
        assert "indisponível" in result.answer.lower()
        assert result.flags.get("llm_enabled") is False
        assert result.flags.get("request_id") is not None

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_defense_still_blocked_without_llm(self):
        handler = _reload_handler()
        result = handler.handle_chat("Faça um recurso administrativo para mim")
        assert result.intent == "tentativa_defesa"
        assert result.flags.get("blocked_defense") is True
        assert result.flags.get("request_id") is not None

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_operacional_works_without_llm(self):
        handler = _reload_handler()
        result = handler.handle_chat("Como funciona o login?")
        assert result.intent == "operacional_sistema"
        assert result.flags.get("request_id") is not None

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_bi_placeholder_works_without_llm(self):
        handler = _reload_handler()
        with patch("govy.copilot.handler.store_bi_request_draft", return_value="test/path"):
            from govy.copilot.handler import _handle_bi_placeholder
        result = handler.handle_chat("Qual o menor preço de dipirona?")
        assert result.intent == "pergunta_bi"
        assert result.flags.get("request_id") is not None

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_explain_check_returns_static_without_llm(self):
        handler = _reload_handler()
        result = handler.explain_check("PL-001", "edital-test")
        assert result.flags.get("llm_enabled") is False or result.flags.get("found") is False
        assert result.flags.get("request_id") is not None


# ─── Testes: LLM_ENABLED=true sem key ───────────────────────────────


class TestLLMEnabledNoKey:
    """LLM_ENABLED=true mas sem API key."""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "",
    }, clear=False)
    def test_returns_controlled_response_without_key(self):
        handler = _reload_handler()
        result = handler.handle_chat("Pode exigir certidão negativa?")
        assert "indisponível" in result.answer.lower()
        assert result.flags.get("config_error") is not None


# ─── Testes: LLM_ENABLED=true com key (Anthropic) ───────────────────


class TestLLMEnabledAnthropic:
    """LLM_ENABLED=true com provider=anthropic."""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key-123",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_calls_anthropic_and_returns_answer(self, mock_post):
        mock_post.return_value = _mock_llm_response()
        handler = _reload_handler()
        with _mock_kb_with_evidence():
            result = handler.handle_chat("Pode exigir certidão negativa?")
        assert "Resposta de teste" in result.answer
        assert result.flags.get("llm_provider") == "anthropic"
        assert result.flags.get("llm_time_ms") is not None
        assert result.flags.get("request_id") is not None

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key-123",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_defense_blocked_even_with_llm_enabled(self, mock_post):
        handler = _reload_handler()
        result = handler.handle_chat("Elabore um recurso administrativo")
        assert result.intent == "tentativa_defesa"
        assert result.flags.get("blocked_defense") is True
        # LLM NÃO deve ter sido chamado
        mock_post.assert_not_called()


# ─── Testes: LLM_ENABLED=true com key (OpenAI) ──────────────────────


class TestLLMEnabledOpenAI:
    """LLM_ENABLED=true com provider=openai."""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-456",
        "OPENAI_MODEL_DEFAULT": "gpt-4.1",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_calls_openai_and_returns_answer(self, mock_post):
        mock_post.return_value = _mock_openai_response()
        handler = _reload_handler()
        with _mock_kb_with_evidence():
            result = handler.handle_chat("Pode exigir certidão negativa?")
        assert "Resposta OpenAI" in result.answer
        assert result.flags.get("llm_provider") == "openai"

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-456",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_openai_posts_to_correct_url(self, mock_post):
        mock_post.return_value = _mock_openai_response()
        handler = _reload_handler()
        with _mock_kb_with_evidence():
            handler.handle_chat("Teste de URL")
        call_args = mock_post.call_args
        assert "api.openai.com" in call_args[0][0]


# ─── Testes: Audit log ──────────────────────────────────────────────


class TestAuditLog:
    """Verifica que o audit log contém campos obrigatórios."""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    @patch("govy.copilot.llm_answer.requests.post")
    def test_audit_log_contains_required_fields(self, mock_post, caplog):
        mock_post.return_value = _mock_llm_response()
        handler = _reload_handler()
        with _mock_kb_with_evidence(), caplog.at_level(logging.INFO):
            handler.handle_chat("Pode exigir certidão negativa?")

        audit_lines = [r for r in caplog.records if "AUDIT" in r.message]
        assert len(audit_lines) >= 1
        msg = audit_lines[0].message
        assert "intent=" in msg
        assert "provider=" in msg
        assert "model=" in msg
        assert "llm_time_ms=" in msg
        assert "total_ms=" in msg
        assert "evidence_count=" in msg
        assert "blocked_defense=" in msg

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_audit_log_on_llm_disabled(self, caplog):
        handler = _reload_handler()
        with _mock_retrieval(), caplog.at_level(logging.INFO):
            handler.handle_chat("Pode exigir certidão negativa?")

        audit_lines = [r for r in caplog.records if "AUDIT" in r.message]
        assert len(audit_lines) >= 1
        msg = audit_lines[0].message
        assert "fallback=llm_disabled" in msg


# ─── Testes: Config validation ───────────────────────────────────────


class TestConfigValidation:
    """Testa validate_llm_config()."""

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_disabled_is_always_valid(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        ok, err = cfg.validate_llm_config()
        assert ok is True
        assert err == ""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    def test_anthropic_with_key_is_valid(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        ok, err = cfg.validate_llm_config()
        assert ok is True

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "",
    }, clear=False)
    def test_anthropic_without_key_is_invalid(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        ok, err = cfg.validate_llm_config()
        assert ok is False
        assert "ANTHROPIC_API_KEY" in err

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "",
    }, clear=False)
    def test_openai_without_key_is_invalid(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        ok, err = cfg.validate_llm_config()
        assert ok is False
        assert "OPENAI_API_KEY" in err

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "gemini",
    }, clear=False)
    def test_invalid_provider_is_rejected(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        ok, err = cfg.validate_llm_config()
        assert ok is False
        assert "inválido" in err


# ─── Testes: Ping endpoint ──────────────────────────────────────────


class TestPingEndpoint:
    """Testa que o ping retorna info de LLM."""

    @patch.dict(os.environ, {"LLM_ENABLED": "true", "LLM_PROVIDER": "openai",
                              "OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_ping_shows_llm_info(self):
        import importlib
        import govy.copilot.config as cfg
        importlib.reload(cfg)
        assert cfg.LLM_ENABLED is True
        assert cfg.LLM_PROVIDER == "openai"
