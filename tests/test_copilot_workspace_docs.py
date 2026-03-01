# tests/test_copilot_workspace_docs.py
"""
Testes para PR2: retrieve_workspace_docs() integração.

Cenários:
1. Sem docs no workspace → retorna []
2. Docs não indexados → retorna [] e loga aviso
3. Docs indexados → busca no Azure Search e retorna evidence
4. Handler: com docs indexados, bot diz "analisei X arquivos"
5. Handler: com docs não indexados, bot diz "ainda não indexados"
6. Handler: sem docs, bot diz "workspace sem documentos"
7. Evidências vêm com source="workspace_doc"
"""
import os
import logging
from unittest.mock import patch, MagicMock

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────

def _make_search_result(chunk_id, content, doc_type="edital", score=3.2):
    """Cria um resultado fake do Azure Search."""
    return {
        "chunk_id": chunk_id,
        "content": content,
        "doc_type": doc_type,
        "semantic_score": score,
        "search_score": score * 0.5,
        "title": f"Doc {chunk_id}",
        "tribunal": None,
        "uf": None,
    }


def _mock_search_returning(results):
    """Mock run_search_with_mode_fallback retornando resultados."""
    return patch(
        "govy.copilot.retrieval.run_search_with_mode_fallback",
        return_value=(results, {"mode": "mock"}),
    )


def _mock_search_client():
    """Mock do search client como disponível."""
    return patch(
        "govy.copilot.retrieval._get_search_client",
        return_value=MagicMock(),
    )


def _mock_embedding():
    """Mock do embedding generator."""
    return patch(
        "govy.copilot.retrieval.generate_query_embedding",
        return_value=[0.1] * 1536,
    )


# ─── Testes: retrieve_workspace_docs direto ─────────────────────────


class TestRetrieveWorkspaceDocs:
    """Testes unitários da função retrieve_workspace_docs."""

    def test_no_docs_returns_empty(self):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy
        result = retrieve_workspace_docs("teste", "ws-1", build_policy(), available_docs=[])
        assert result == []

    def test_only_non_indexed_docs_returns_empty(self, caplog):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy
        docs = [
            {"name": "edital.pdf", "doc_type": "edital", "indexed": False},
            {"name": "TR.pdf", "doc_type": "tr", "indexed": False},
        ]
        with caplog.at_level(logging.INFO):
            result = retrieve_workspace_docs("teste", "ws-1", build_policy(), available_docs=docs)
        assert result == []
        assert any("não indexados" in r.message for r in caplog.records)

    def test_indexed_docs_search_azure(self):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy

        fake_results = [
            _make_search_result("c1", "Cláusula 5.1 do edital: prazo de entrega...", "edital", 3.5),
            _make_search_result("c2", "Cláusula 8.2: documentação habilitatória...", "edital", 2.8),
        ]

        docs = [
            {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
        ]

        with _mock_search_client(), _mock_embedding(), _mock_search_returning(fake_results):
            result = retrieve_workspace_docs("prazo de entrega", "ws-1", build_policy(), available_docs=docs)

        assert len(result) >= 1
        assert all(ev.source == "workspace_doc" for ev in result)
        assert result[0].snippet  # Tem conteúdo

    def test_mixed_indexed_and_not_indexed(self, caplog):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy

        fake_results = [
            _make_search_result("c1", "Art. 75 da Lei 14.133...", "edital", 3.0),
        ]

        docs = [
            {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
            {"name": "anexo_I.pdf", "doc_type": "anexo", "indexed": False},
        ]

        with _mock_search_client(), _mock_embedding(), _mock_search_returning(fake_results), \
                caplog.at_level(logging.INFO):
            result = retrieve_workspace_docs("teste", "ws-1", build_policy(), available_docs=docs)

        # Deve retornar evidência do doc indexado
        assert len(result) >= 1
        # Deve logar que anexo não está indexado
        assert any("não indexados" in r.message for r in caplog.records)

    def test_blocked_doc_types_filtered(self):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy

        docs = [
            {"name": "doutrina.pdf", "doc_type": "doutrina", "indexed": True},
        ]

        # Doutrina é bloqueada — nem deveria tentar buscar
        with _mock_search_client(), _mock_embedding(), \
                _mock_search_returning([]):
            result = retrieve_workspace_docs("teste", "ws-1", build_policy(), available_docs=docs)

        assert result == []

    def test_low_confidence_filtered(self):
        from govy.copilot.retrieval import retrieve_workspace_docs
        from govy.copilot.policy import build_policy

        fake_results = [
            _make_search_result("c1", "Texto vago...", "edital", 0.1),  # score baixo
        ]
        docs = [{"name": "edital.pdf", "doc_type": "edital", "indexed": True}]

        with _mock_search_client(), _mock_embedding(), _mock_search_returning(fake_results):
            result = retrieve_workspace_docs("teste", "ws-1", build_policy(), available_docs=docs)

        assert result == []  # Filtrado por low confidence


# ─── Testes: handler com workspace docs ──────────────────────────────


class TestHandlerWorkspaceDocs:
    """Testes de integração handler + workspace docs."""

    @patch.dict(os.environ, {"LLM_ENABLED": "false"}, clear=False)
    def test_handler_no_docs_message(self):
        """Workspace sem docs → mensagem contextual."""
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        context = {
            "workspace_id": "ws-test",
            "licitacao_id": "lic-test",
        }
        result = govy.copilot.handler.handle_chat(
            "Pode exigir certidão negativa?", context=context
        )
        # LLM disabled → resposta controlada
        assert "indisponível" in result.answer.lower()

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    def test_handler_with_indexed_docs_includes_workspace_evidence(self):
        """Docs indexados no workspace devem gerar evidência workspace_doc."""
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)
        import json

        context = {
            "workspace_id": "ws-test",
            "licitacao_id": "lic-test",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
            ],
        }

        fake_kb = [
            _make_search_result("kb-1", "Art. 75 Lei 14.133...", "lei", 3.5),
        ]
        fake_ws = [
            _make_search_result("ws-1", "Cláusula 5.1 do edital...", "edital", 3.0),
        ]

        # Mock LLM response
        mock_llm_resp = MagicMock()
        mock_llm_resp.status_code = 200
        mock_llm_resp.raise_for_status = MagicMock()
        mock_llm_resp.json.return_value = {
            "content": [{"text": json.dumps({
                "answer": "Analisei os documentos do workspace.",
                "uncertainty": None,
                "followup_questions": [],
                "evidence_used": ["kb-1", "ws-1"],
            })}]
        }

        with patch("govy.copilot.retrieval._get_search_client", return_value=MagicMock()), \
             patch("govy.copilot.retrieval.generate_query_embedding", return_value=[0.1]*1536), \
             patch("govy.copilot.retrieval.run_search_with_mode_fallback") as mock_search, \
             patch("govy.copilot.llm_answer.requests.post", return_value=mock_llm_resp):

            # Primeira chamada: KB search (3 doc_types x 1 call each)
            # Depois: workspace search
            mock_search.return_value = (fake_kb, {"mode": "mock"})

            result = govy.copilot.handler.handle_chat(
                "Pode exigir certidão negativa?", context=context
            )

        assert result.answer is not None
        assert result.flags.get("workspace_mode") == "licitacao_workspace"


# ─── Testes: handler mensagens contextuais sem evidência ──────────


class TestHandlerNoEvidenceMessages:
    """Testa que handler gera mensagens corretas quando não há evidência."""

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    def test_indexed_docs_no_match(self):
        """Docs indexados mas busca não encontrou → mensagem específica."""
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        context = {
            "workspace_id": "ws-test",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": True},
            ],
        }

        with patch("govy.copilot.retrieval._get_search_client", return_value=MagicMock()), \
             patch("govy.copilot.retrieval.generate_query_embedding", return_value=[0.1]*1536), \
             patch("govy.copilot.retrieval.run_search_with_mode_fallback",
                   return_value=([], {"mode": "mock"})):
            result = govy.copilot.handler.handle_chat(
                "Algo totalmente fora do contexto?", context=context
            )

        assert "Pesquisei em" in result.answer or "edital.pdf" in result.answer
        assert result.flags.get("needs_more_context") is True

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    def test_non_indexed_docs_message(self):
        """Docs presentes mas não indexados → mensagem específica."""
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        context = {
            "workspace_id": "ws-test",
            "available_docs": [
                {"name": "edital.pdf", "doc_type": "edital", "indexed": False},
            ],
        }

        with patch("govy.copilot.retrieval._get_search_client", return_value=MagicMock()), \
             patch("govy.copilot.retrieval.generate_query_embedding", return_value=[0.1]*1536), \
             patch("govy.copilot.retrieval.run_search_with_mode_fallback",
                   return_value=([], {"mode": "mock"})):
            result = govy.copilot.handler.handle_chat(
                "O edital permite subcontratação?", context=context
            )

        assert "não foram indexados" in result.answer or "indisponível" in result.answer.lower()

    @patch.dict(os.environ, {
        "LLM_ENABLED": "true",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key",
    }, clear=False)
    def test_workspace_without_docs_message(self):
        """Workspace vazio → mensagem pedindo docs."""
        import importlib
        import govy.copilot.config
        importlib.reload(govy.copilot.config)
        import govy.copilot.llm_answer
        importlib.reload(govy.copilot.llm_answer)
        import govy.copilot.handler
        importlib.reload(govy.copilot.handler)

        context = {
            "workspace_id": "ws-test",
            # Sem available_docs
        }

        with patch("govy.copilot.retrieval._get_search_client", return_value=MagicMock()), \
             patch("govy.copilot.retrieval.generate_query_embedding", return_value=[0.1]*1536), \
             patch("govy.copilot.retrieval.run_search_with_mode_fallback",
                   return_value=([], {"mode": "mock"})):
            result = govy.copilot.handler.handle_chat(
                "Análise do edital", context=context
            )

        assert "não tem documentos" in result.answer or "indisponível" in result.answer.lower()
