# tests/test_copilot_bi_placeholder.py
"""
Testes do fluxo BI Placeholder do Copiloto.

Critérios de aceite:
- Perguntas BI retornam bi_pending=True
- bi_request_draft preenchido (mesmo com campos nulos)
- 3 follow-ups (produto, local/plataforma, período)
- Nenhuma resposta BI contém números/estimativas
- bi_request_draft é persistido (mock)
- metric_type mapeado corretamente
"""
import os
import re
import json
import uuid
import unittest
from unittest.mock import patch, MagicMock

# Garantir BI_ENABLED=false para os testes
os.environ["BI_ENABLED"] = "false"

from govy.copilot.router import (
    detect_intent,
    detect_bi_metric_type,
    detect_bi_platform,
    detect_bi_time_preset,
)
from govy.copilot.contracts import BiRequestDraft, CopilotOutput


# ==============================================================================
# Helpers
# ==============================================================================

# Detecta números que representam valores monetários, percentuais ou quantidades.
# NÃO casa com números soltos de 1-2 dígitos (ex.: "3 follow-ups" ou datas).
# Casa: R$10, R$ 1.500,00, 12.5%, 1500, 3.200
# Não casa: "item 5", "12 meses", "2024-2025", "500mg"
_NUMBER_RE = re.compile(
    r"(?:R\$\s*)\d[\d.,]*"           # R$ seguido de número (sempre é valor)
    r"|\b\d[\d.,]*\s*%"              # número seguido de % (sempre é métrica)
    r"|\b\d{4,}(?:[.,]\d+)?\b"      # número >= 4 dígitos (ex.: 1500, 3.200)
)


def _call_handler(user_text: str, context: dict = None):
    """Chama handle_chat com mocks de infra (blob, Azure Search, LLM)."""
    with patch("govy.copilot.handler.store_bi_request_draft") as mock_store, \
         patch.dict(os.environ, {"BI_ENABLED": "false"}):
        mock_store.return_value = "kb-content/bi/requests/2026-02-28/test.json"
        from govy.copilot.handler import handle_chat
        result = handle_chat(user_text, context or {})
        return result, mock_store


# ==============================================================================
# Test: Router — detecção de intent BI
# ==============================================================================

class TestBiIntentDetection(unittest.TestCase):

    def test_menor_preco(self):
        self.assertEqual(detect_intent("qual o menor preço da dipirona?"), "pergunta_bi")

    def test_maior_preco(self):
        self.assertEqual(detect_intent("maior preço de notebook em SP"), "pergunta_bi")

    def test_media_propostas(self):
        self.assertEqual(detect_intent("quantas propostas em média em Salvador?"), "pergunta_bi")

    def test_reducao_disputa(self):
        self.assertEqual(detect_intent("qual % de redução na disputa?"), "pergunta_bi")

    def test_preco_previsto(self):
        self.assertEqual(detect_intent("qual o preço previsto do item 12?"), "pergunta_bi")

    def test_participantes(self):
        self.assertEqual(detect_intent("quantas empresas devem participar?"), "pergunta_bi")

    def test_historico(self):
        self.assertEqual(detect_intent("histórico de preço de caneta"), "pergunta_bi")

    def test_ticket_medio(self):
        self.assertEqual(detect_intent("qual o ticket médio?"), "pergunta_bi")

    def test_por_plataforma(self):
        self.assertEqual(detect_intent("dados por plataforma PNCP"), "pergunta_bi")

    def test_pergunta_juridica_nao_e_bi(self):
        self.assertNotEqual(detect_intent("pode exigir atestado de capacidade técnica?"), "pergunta_bi")


# ==============================================================================
# Test: Router — metric_type mapping
# ==============================================================================

class TestBiMetricTypeMapping(unittest.TestCase):

    def test_min_price(self):
        self.assertEqual(detect_bi_metric_type("qual o menor preço da dipirona 500mg?"), "min_price")

    def test_max_price(self):
        self.assertEqual(detect_bi_metric_type("maior preço de notebook"), "max_price")

    def test_avg_price_ticket_medio(self):
        self.assertEqual(detect_bi_metric_type("qual o ticket médio?"), "avg_price")

    def test_avg_price_preco_medio(self):
        self.assertEqual(detect_bi_metric_type("preço médio de caneta"), "avg_price")

    def test_avg_bids(self):
        self.assertEqual(detect_bi_metric_type("média de propostas em Salvador"), "avg_bids")

    def test_price_drop_pct(self):
        self.assertEqual(detect_bi_metric_type("qual % de redução na disputa?"), "price_drop_pct")

    def test_expected_price(self):
        self.assertEqual(detect_bi_metric_type("preço previsto do item"), "expected_price")

    def test_expected_price_not_ticket_medio(self):
        """ticket médio NÃO é expected_price — é avg_price."""
        self.assertNotEqual(detect_bi_metric_type("ticket médio"), "expected_price")

    def test_participants_forecast(self):
        self.assertEqual(detect_bi_metric_type("quantas empresas devem participar?"), "participants_forecast")

    def test_unknown_returns_other(self):
        self.assertEqual(detect_bi_metric_type("me dá um dado qualquer"), "other")


# ==============================================================================
# Test: Router — platform detection
# ==============================================================================

class TestBiPlatformDetection(unittest.TestCase):

    def test_pncp(self):
        self.assertEqual(detect_bi_platform("no PNCP nos últimos 12 meses"), "pncp")

    def test_comprasnet(self):
        self.assertEqual(detect_bi_platform("preço no Comprasnet"), "comprasnet")

    def test_bec(self):
        self.assertEqual(detect_bi_platform("bolsa eletrônica de compras"), "bec")

    def test_unknown(self):
        self.assertEqual(detect_bi_platform("qualquer plataforma"), "unknown")


# ==============================================================================
# Test: Router — time preset detection
# ==============================================================================

class TestBiTimePresetDetection(unittest.TestCase):

    def test_last_12m(self):
        self.assertEqual(detect_bi_time_preset("nos últimos 12 meses"), "last_12m")

    def test_last_6m(self):
        self.assertEqual(detect_bi_time_preset("últimos 6 meses"), "last_6m")

    def test_last_24m(self):
        self.assertEqual(detect_bi_time_preset("últimos 2 anos"), "last_24m")

    def test_none_when_no_match(self):
        self.assertIsNone(detect_bi_time_preset("desde sempre"))


# ==============================================================================
# Test: Handler — fluxo BI placeholder completo
# ==============================================================================

class TestBiPlaceholderHandler(unittest.TestCase):
    """Testa o fluxo completo do handler quando BI está desabilitado."""

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_caso1_dipirona_curitiba_pncp_12m(self, mock_container):
        """Caso 1: Menor preço dipirona 500mg em Curitiba no PNCP últimos 12 meses."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat(
            "Qual o menor preço da dipirona 500mg em Curitiba no PNCP nos últimos 12 meses?",
            {}
        )

        self.assertTrue(result.bi_pending)
        self.assertIsNotNone(result.bi_request_draft)
        self.assertEqual(result.bi_request_draft.metric_type, "min_price")
        self.assertEqual(result.bi_request_draft.platform, "pncp")
        self.assertEqual(result.bi_request_draft.time_range.preset, "last_12m")
        self.assertEqual(len(result.followup_questions), 3)
        self.assertFalse(_NUMBER_RE.search(result.answer), "Resposta NÃO deve conter números")

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_caso2_media_propostas_salvador(self, mock_container):
        """Caso 2: Média de propostas em Salvador para leite em pó no Comprasnet."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat(
            "Quantas propostas em média em Salvador para leite em pó no Comprasnet?",
            {}
        )

        self.assertTrue(result.bi_pending)
        self.assertEqual(result.bi_request_draft.metric_type, "avg_bids")
        self.assertEqual(result.bi_request_draft.platform, "comprasnet")
        self.assertIn("time_range", result.bi_request_draft.needs_user_input)
        self.assertEqual(len(result.followup_questions), 3)
        self.assertFalse(_NUMBER_RE.search(result.answer))

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_caso3_reducao_disputa_com_workspace(self, mock_container):
        """Caso 3: Redução na disputa com workspace ativo."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat(
            "Qual foi a redução de preço na fase de disputa dessa licitação?",
            {"workspace_id": "ws-123", "licitacao_id": "lic-456", "uf": "PR"}
        )

        self.assertTrue(result.bi_pending)
        self.assertEqual(result.bi_request_draft.metric_type, "price_drop_pct")
        self.assertEqual(result.bi_request_draft.workspace_id, "ws-123")
        self.assertEqual(result.bi_request_draft.licitacao_id, "lic-456")
        # uf preenchido do contexto, não deve pedir city_or_uf
        self.assertNotIn("city_or_uf", result.bi_request_draft.needs_user_input)
        self.assertEqual(len(result.followup_questions), 3)
        self.assertFalse(_NUMBER_RE.search(result.answer))

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_caso4_preco_previsto_item(self, mock_container):
        """Caso 4: Preço previsto do item 12."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("Qual o preço previsto do item 12?", {})

        self.assertTrue(result.bi_pending)
        self.assertEqual(result.bi_request_draft.metric_type, "expected_price")
        self.assertIn("product_query", result.bi_request_draft.needs_user_input)
        self.assertEqual(len(result.followup_questions), 3)
        self.assertFalse(_NUMBER_RE.search(result.answer))

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_caso5_participantes_licitacao(self, mock_container):
        """Caso 5: Quantas empresas devem participar."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("Quantas empresas devem participar dessa licitação?", {})

        self.assertTrue(result.bi_pending)
        self.assertEqual(result.bi_request_draft.metric_type, "participants_forecast")
        self.assertEqual(len(result.followup_questions), 3)
        self.assertFalse(_NUMBER_RE.search(result.answer))


# ==============================================================================
# Test: Nenhuma resposta BI contém números
# ==============================================================================

class TestBiNeverReturnsNumbers(unittest.TestCase):
    """Garante que nenhuma pergunta BI retorna números quando BI está off."""

    BI_QUESTIONS = [
        "qual o menor preço da dipirona?",
        "quantas propostas em média?",
        "% de redução na disputa",
        "preço previsto do item 5",
        "quantas empresas devem participar?",
        "histórico de preço de leite em pó",
        "ticket médio de caneta esferográfica",
        "dispersão de preços de notebook em SP",
    ]

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_no_numbers_in_any_bi_response(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat

        for question in self.BI_QUESTIONS:
            result = handle_chat(question, {})
            self.assertTrue(result.bi_pending, f"bi_pending deve ser True para: {question}")
            self.assertFalse(
                _NUMBER_RE.search(result.answer),
                f"Resposta NÃO deve conter números para: {question}\nResposta: {result.answer}"
            )


# ==============================================================================
# Test: Follow-ups sempre 3
# ==============================================================================

class TestBiAlwaysThreeFollowups(unittest.TestCase):

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_always_three_followups(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat

        questions = [
            "menor preço de dipirona",
            "quantas empresas participam no PNCP nos últimos 12 meses em SP?",
            "preço previsto do item",
        ]
        for q in questions:
            result = handle_chat(q, {})
            self.assertEqual(
                len(result.followup_questions), 3,
                f"Deve ter exatamente 3 follow-ups para: {q}"
            )

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_followup_order_produto_local_plataforma(self, mock_container):
        """Follow-ups na ordem: produto → local → plataforma."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        fups = result.followup_questions
        # 1o: produto
        self.assertIn("item", fups[0].lower())
        # 2o: local
        self.assertTrue(
            "local" in fups[1].lower() or "cidade" in fups[1].lower() or "uf" in fups[1].lower(),
            f"2o follow-up deve ser sobre local, got: {fups[1]}"
        )
        # 3o: plataforma
        self.assertTrue(
            "plataforma" in fups[2].lower() or "pncp" in fups[2].lower(),
            f"3o follow-up deve ser sobre plataforma, got: {fups[2]}"
        )

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_followups_no_period_question(self, mock_container):
        """Período NÃO aparece nos 3 follow-ups (fica para próximo turno)."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        for fup in result.followup_questions:
            self.assertNotIn("período", fup.lower(),
                             f"Período não deve estar nos follow-ups: {fup}")


# ==============================================================================
# Test: bi_request_draft sempre presente e com needs_user_input coerente
# ==============================================================================

class TestBiDraftConsistency(unittest.TestCase):

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_draft_has_request_id(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})
        self.assertIsNotNone(result.bi_request_draft)
        self.assertTrue(len(result.bi_request_draft.request_id) > 0)

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_draft_has_created_at(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})
        self.assertIn("T", result.bi_request_draft.created_at_utc)

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_draft_needs_input_always_has_product(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})
        self.assertIn("product_query", result.bi_request_draft.needs_user_input)

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_draft_context_fills_uf(self, mock_container):
        """Se contexto tem UF, draft não pede city_or_uf."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de caneta", {"uf": "SP"})
        self.assertNotIn("city_or_uf", result.bi_request_draft.needs_user_input)
        self.assertEqual(result.bi_request_draft.location.uf, "SP")

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_product_query_raw_starts_empty(self, mock_container):
        """product_query.raw deve ser '' (não o user_text inteiro)."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("Qual o menor preço da dipirona 500mg em Curitiba?", {})
        self.assertEqual(result.bi_request_draft.product_query.raw, "")

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_user_question_raw_has_full_text(self, mock_container):
        """user_question_raw preserva o texto original completo."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        question = "Qual o menor preço da dipirona 500mg em Curitiba?"
        result = handle_chat(question, {})
        self.assertEqual(result.bi_request_draft.user_question_raw, question)


# ==============================================================================
# Test: Persistência (mock)
# ==============================================================================

class TestBiDraftPersistence(unittest.TestCase):

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_store_called_on_bi_placeholder(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        # Verifica que upload_blob foi chamado
        mock_blob.upload_blob.assert_called_once()
        call_args = mock_blob.upload_blob.call_args
        payload = json.loads(call_args[0][0])
        self.assertEqual(payload["metric_type"], "min_price")
        self.assertIn("request_id", payload)

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_blob_path_in_flags(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        self.assertIn("bi_draft_blob_path", result.flags)
        self.assertIsNotNone(result.flags["bi_draft_blob_path"])

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_persisted_flag_true_on_success(self, mock_container):
        """bi_draft_persisted=True quando blob salva com sucesso."""
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        self.assertTrue(result.flags["bi_draft_persisted"])
        self.assertIsNone(result.flags["bi_draft_error"])

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_persisted_flag_false_on_failure(self, mock_container):
        """bi_draft_persisted=False e bi_draft_error preenchido quando blob falha."""
        mock_container.side_effect = Exception("Blob Storage offline")

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})

        # Deve continuar retornando bi_pending e draft (sem crash)
        self.assertTrue(result.bi_pending)
        self.assertIsNotNone(result.bi_request_draft)
        self.assertFalse(result.flags["bi_draft_persisted"])
        self.assertIsNotNone(result.flags["bi_draft_error"])


# ==============================================================================
# Test: to_dict / to_json_response incluem bi fields
# ==============================================================================

class TestBiOutputSerialization(unittest.TestCase):

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_to_dict_includes_bi_pending(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})
        d = result.to_dict()
        self.assertTrue(d["bi_pending"])
        self.assertIn("bi_request_draft", d)
        self.assertEqual(d["bi_request_draft"]["metric_type"], "min_price")

    @patch("govy.copilot.bi_request_store.get_container_client")
    def test_to_json_response_structure(self, mock_container):
        mock_blob = MagicMock()
        mock_container.return_value.get_blob_client.return_value = mock_blob

        from govy.copilot.handler import handle_chat
        result = handle_chat("menor preço de dipirona", {})
        resp = result.to_json_response()
        self.assertEqual(resp["status"], "success")
        self.assertTrue(resp["copilot"]["bi_pending"])


if __name__ == "__main__":
    unittest.main()
