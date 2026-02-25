# tests/test_legal_db_writer.py
"""
Testes para o DB writer.
Testes de UPSERT idempotencia requerem Postgres (skip se POSTGRES_CONNSTR nao definida).
Testes de logica de SQL param construction rodam sem DB.
"""
from __future__ import annotations

import os
import pytest

from govy.legal.models import LegalDocumentRow, LegalProvision, LegalChunk

# Skip all DB tests if no Postgres available
pytestmark = pytest.mark.skipif(
    not os.environ.get("POSTGRES_CONNSTR"),
    reason="POSTGRES_CONNSTR nao definida — skip DB tests"
)


@pytest.fixture
def sample_doc():
    """Cria um LegalDocumentRow de teste."""
    provisions = [
        LegalProvision(
            provision_key="art_1",
            label="Art. 1o",
            provision_type="artigo",
            parent_key=None,
            hierarchy_path=["Art. 1o"],
            order_in_doc=1,
            content="Art. 1o Texto do artigo.",
        ),
        LegalProvision(
            provision_key="art_1_par_1",
            label="Par. 1o",
            provision_type="paragrafo",
            parent_key="art_1",
            hierarchy_path=["Art. 1o", "Par. 1o"],
            order_in_doc=2,
            content="",
        ),
    ]
    chunks = [
        LegalChunk(
            chunk_id="test_doc__art_1__0",
            doc_id="test_doc",
            provision_key="art_1",
            order_in_doc=0,
            content="Art. 1o Texto do artigo.\n§ 1o Paragrafo do artigo.",
            content_hash="abc123def456",
            char_count=52,
            citation_short="Lei Teste, Art. 1o",
            hierarchy_path=["Art. 1o"],
        ),
    ]
    return LegalDocumentRow(
        doc_id="test_doc",
        jurisdiction_id="federal_br",
        doc_type="lei",
        number="99999",
        year=2025,
        title="Lei de Teste 99999/2025",
        source_blob_path="normas-juridicas-raw/test.pdf",
        source_format="pdf",
        text_sha256="deadbeef" * 8,
        char_count=1000,
        provisions=provisions,
        chunks=chunks,
    )


class TestDbWriter:
    def test_write_and_rewrite_idempotent(self, sample_doc):
        """UPSERT deve ser idempotente — gravar 2x sem erro."""
        from govy.legal.db_writer import write_document

        # Primeira gravacao
        result1 = write_document(sample_doc)
        assert result1["provisions"] == 2
        assert result1["chunks"] == 1

        # Segunda gravacao (idempotente)
        result2 = write_document(sample_doc)
        assert result2["provisions"] == 2
        assert result2["chunks"] == 1

    def test_write_updates_existing(self, sample_doc):
        """UPSERT deve atualizar dados quando doc_id ja existe."""
        from govy.legal.db_writer import write_document

        # Primeira gravacao
        write_document(sample_doc)

        # Modifica titulo
        sample_doc.title = "Lei de Teste ATUALIZADA"
        result = write_document(sample_doc)
        assert result["provisions"] == 2

    def test_orphan_removal(self, sample_doc):
        """Remove provisions/chunks que nao existem mais no doc."""
        from govy.legal.db_writer import write_document

        # Grava com 2 provisions
        write_document(sample_doc)

        # Remove uma provision e regrava
        sample_doc.provisions = [sample_doc.provisions[0]]
        result = write_document(sample_doc)
        assert result["orphans_removed"] >= 1

    def _cleanup(self, sample_doc):
        """Remove dados de teste do DB."""
        from govy.db.connection import get_conn, release_conn
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM legal_chunk WHERE doc_id = %s", (sample_doc.doc_id,))
                cur.execute("DELETE FROM legal_provision WHERE doc_id = %s", (sample_doc.doc_id,))
                cur.execute("DELETE FROM legal_document WHERE doc_id = %s", (sample_doc.doc_id,))
            conn.commit()
        finally:
            release_conn(conn)
