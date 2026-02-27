"""
GOVY - Doctrine v2 Contract Tests
==================================
Modo cheap (default): valida JSON ja processado (custo zero, <5s)
Modo full: reprocessa DOCX via pipeline (custa OpenAI, ~60s)

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
  DOCTRINE_TEST_PROCESSED_BLOB_NAME  (modo cheap - JSON v2 no doutrina-processed)
  DOCTRINE_TEST_BLOB_NAME            (modo full - DOCX no doutrina)
  DOCTRINE_TEST_MODE                 (cheap|full, default=cheap)
"""

import json
import os
import unittest
from typing import Any, Dict


ARGUMENT_ROLE_CATALOG_V1 = {
    "DEFINICAO",
    "FINALIDADE",
    "DISTINCAO",
    "LIMITE",
    "RISCO",
    "CRITERIO",
    "PASSO_A_PASSO",
}

# scope_assertions esperadas no contrato v2
EXPECTED_SCOPE_KEYS = {
    "decide_caso_concreto",
    "substitui_jurisprudencia",
    "afirma_consenso",
    "revela_autoria",
}

# Prefixos PROIBIDOS para tese_neutra (mais robusto que lista de permitidos)
FORBIDDEN_TESE_STARTS = (
    "E obrigatorio",
    "Deve-se",
    "A lei exige",
    "O tribunal determinou",
    "O TCU decidiu",
    "O STJ entende",
    "A jurisprudencia",
    "E pacifico",
    "E consenso",
    "E unanime",
)


def _get_conn() -> str:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING/AzureWebJobsStorage")
    return conn


class TestDoctrineV2Contract(unittest.TestCase):
    """
    Valida contrato doctrine_processed_v2.

    Modo cheap (default):
      - Baixa blob JSON ja processado
      - Valida estrutura/campos
      - Custo: ZERO, Tempo: <5s

    Modo full (DOCTRINE_TEST_MODE=full):
      - Reprocessa DOCX via pipeline
      - Valida output completo
      - Custo: ~$0.01-0.05 (OpenAI), Tempo: ~60s
    """

    def setUp(self):
        self.conn = _get_conn()

        from azure.storage.blob import BlobServiceClient
        self.blob_service = BlobServiceClient.from_connection_string(self.conn)

        self.processed_container = os.getenv(
            "DOCTRINE_PROCESSED_CONTAINER_NAME", "kb-doutrina-processed"
        )
        self.source_container = os.getenv("DOCTRINE_CONTAINER_NAME", "kb-doutrina-raw")
        self.mode = (os.getenv("DOCTRINE_TEST_MODE") or "cheap").strip().lower()

        self.processed_blob = (
            os.getenv("DOCTRINE_TEST_PROCESSED_BLOB_NAME") or ""
        ).strip()
        self.source_blob = (os.getenv("DOCTRINE_TEST_BLOB_NAME") or "").strip()

        if self.mode == "full":
            if not self.source_blob:
                self.skipTest(
                    "DOCTRINE_TEST_MODE=full requer DOCTRINE_TEST_BLOB_NAME"
                )
        else:
            if not self.processed_blob:
                self.skipTest(
                    "Modo cheap requer DOCTRINE_TEST_PROCESSED_BLOB_NAME"
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _download_json(self, container: str, blob_name: str) -> Dict[str, Any]:
        client = self.blob_service.get_container_client(container)
        data = client.get_blob_client(blob_name).download_blob().readall()
        return json.loads(data)

    # ------------------------------------------------------------------
    # Validacao do contrato (reutilizada por cheap e full)
    # ------------------------------------------------------------------

    def _assert_contract(self, payload: Dict[str, Any]):
        # 1. kind
        self.assertEqual(
            payload.get("kind"),
            "doctrine_processed_v2",
            "kind deve ser doctrine_processed_v2",
        )

        # 2. context.tema_principal UPPER
        ctx = payload.get("context") or {}
        tema = (ctx.get("tema_principal") or "").strip()
        self.assertTrue(
            tema != "" and tema == tema.upper(),
            f"context.tema_principal deve ser UPPER e nao vazio, got: '{tema}'",
        )

        # 3. context.etapa_processo UPPER
        etapa = (ctx.get("etapa_processo") or "").strip()
        self.assertTrue(
            etapa != "",
            f"context.etapa_processo nao pode ser vazio, got: '{etapa}'",
        )

        # 4. source.source_sha 64 chars
        source = payload.get("source") or {}
        sha = source.get("source_sha") or ""
        self.assertEqual(
            len(sha), 64,
            f"source_sha deve ter 64 chars (SHA256), got {len(sha)}",
        )

        # 5. raw_chunks nao vazio + tema_principal UPPER
        raw_chunks = payload.get("raw_chunks") or []
        self.assertTrue(len(raw_chunks) > 0, "raw_chunks nao pode ser vazio")
        for i, rc in enumerate(raw_chunks):
            rc_tema = (rc.get("tema_principal") or "").strip()
            self.assertEqual(
                rc_tema, rc_tema.upper(),
                f"raw_chunks[{i}].tema_principal deve ser UPPER, got: '{rc_tema}'",
            )

        # 6. semantic_chunks - validacao detalhada
        semantic = payload.get("semantic_chunks") or []
        for i, ch in enumerate(semantic):
            prefix = f"semantic_chunks[{i}]"

            # 6a. procedural_stage UPPER
            ps = (ch.get("procedural_stage") or "").strip()
            self.assertTrue(
                ps != "" and ps == ps.upper(),
                f"{prefix}.procedural_stage deve ser UPPER, got: '{ps}'",
            )

            # 6b. scope_assertions deve existir, ter as 4 chaves, todas False
            sa = ch.get("scope_assertions")
            self.assertIsNotNone(sa, f"{prefix}.scope_assertions ausente")
            self.assertIsInstance(sa, dict, f"{prefix}.scope_assertions deve ser dict")
            for key in EXPECTED_SCOPE_KEYS:
                self.assertIn(key, sa, f"{prefix}.scope_assertions falta chave '{key}'")
                self.assertFalse(
                    sa[key],
                    f"{prefix}.scope_assertions.{key} deve ser False, got {sa[key]}",
                )

            # 6c. tese_neutra NAO pode comecar com frases assertivas
            tese = (ch.get("tese_neutra") or "").strip()
            if tese:
                for forbidden in FORBIDDEN_TESE_STARTS:
                    self.assertFalse(
                        tese.startswith(forbidden),
                        f"{prefix}.tese_neutra comeca com frase proibida: '{forbidden}'. "
                        f"Texto: {tese[:80]}",
                    )

            # 6d. argument_role: catalogo v1 ou None quando INCERTO
            coverage = (ch.get("coverage_status") or "").strip().upper()
            role = ch.get("argument_role")
            if coverage == "INCERTO":
                self.assertIsNone(
                    role,
                    f"{prefix}: INCERTO => argument_role deve ser null, got '{role}'",
                )
            else:
                if role is not None:
                    role_upper = str(role).strip().upper()
                    self.assertIn(
                        role_upper,
                        ARGUMENT_ROLE_CATALOG_V1,
                        f"{prefix}: argument_role invalido: '{role}'",
                    )

    # ------------------------------------------------------------------
    # Teste principal
    # ------------------------------------------------------------------

    def test_contract(self):
        if self.mode == "full":
            from govy.doctrine.pipeline import (
                DoctrineIngestRequest,
                ingest_doctrine_process_once,
            )

            req = DoctrineIngestRequest(
                blob_name=self.source_blob,
                etapa_processo="habilitacao",
                tema_principal="habilitacao",
                force_reprocess=True,
            )

            result = ingest_doctrine_process_once(
                blob_service=self.blob_service,
                container_source=self.source_container,
                container_processed=self.processed_container,
                req=req,
            )

            # Valida response do pipeline
            self.assertIn("status", result)
            self.assertIn(result["status"], {"processed", "already_processed"})
            self.assertIn("source", result)
            self.assertIn("processed", result)

            src = result["source"]
            self.assertEqual(
                len(src.get("source_sha", "")), 64,
                "response source_sha deve ter 64 chars",
            )

            proc = result["processed"]
            proc_blob = proc.get("blob_name", "")
            self.assertTrue(proc_blob.endswith(".json"), "processed.blob_name deve terminar com .json")
            self.assertIn("/", proc_blob, "processed.blob_name deve ser path completo")

            # Baixa e valida conteudo
            payload = self._download_json(self.processed_container, proc_blob)
            self._assert_contract(payload)

        else:
            # Modo cheap: valida JSON existente (custo zero)
            payload = self._download_json(
                self.processed_container, self.processed_blob
            )
            self._assert_contract(payload)


if __name__ == "__main__":
    unittest.main()
