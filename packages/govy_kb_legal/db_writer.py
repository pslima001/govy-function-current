# govy/legal/db_writer.py
"""
Escritor de documentos legais no Postgres.

UPSERT idempotente (ON CONFLICT) para legal_document, legal_provision, legal_chunk.
Transacao atomica por documento — se qualquer parte falhar, rollback completo.
"""
from __future__ import annotations

import logging
from typing import List

from govy.db.connection import get_conn, release_conn
from .models import LegalDocumentRow, LegalProvision, LegalChunk

logger = logging.getLogger(__name__)

# ── SQL statements ────────────────────────────────────────────────────────────

UPSERT_DOCUMENT = """
INSERT INTO legal_document (
    doc_id, jurisdiction_id, doc_type, number, year, title,
    source_blob_path, source_format, text_sha256, char_count,
    provision_count, chunk_count, status, updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, now()
)
ON CONFLICT (doc_id) DO UPDATE SET
    jurisdiction_id  = EXCLUDED.jurisdiction_id,
    doc_type         = EXCLUDED.doc_type,
    number           = EXCLUDED.number,
    year             = EXCLUDED.year,
    title            = EXCLUDED.title,
    source_blob_path = EXCLUDED.source_blob_path,
    source_format    = EXCLUDED.source_format,
    text_sha256      = EXCLUDED.text_sha256,
    char_count       = EXCLUDED.char_count,
    provision_count  = EXCLUDED.provision_count,
    chunk_count      = EXCLUDED.chunk_count,
    status           = EXCLUDED.status,
    updated_at       = now()
"""

UPSERT_PROVISION = """
INSERT INTO legal_provision (
    doc_id, provision_key, label, provision_type,
    parent_key, hierarchy_path, order_in_doc
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s
)
ON CONFLICT (doc_id, provision_key) DO UPDATE SET
    label          = EXCLUDED.label,
    provision_type = EXCLUDED.provision_type,
    parent_key     = EXCLUDED.parent_key,
    hierarchy_path = EXCLUDED.hierarchy_path,
    order_in_doc   = EXCLUDED.order_in_doc
"""

UPSERT_CHUNK = """
INSERT INTO legal_chunk (
    chunk_id, doc_id, provision_key, order_in_doc,
    content, content_hash, char_count,
    citation_short, hierarchy_path
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s
)
ON CONFLICT (chunk_id) DO UPDATE SET
    doc_id         = EXCLUDED.doc_id,
    provision_key  = EXCLUDED.provision_key,
    order_in_doc   = EXCLUDED.order_in_doc,
    content        = EXCLUDED.content,
    content_hash   = EXCLUDED.content_hash,
    char_count     = EXCLUDED.char_count,
    citation_short = EXCLUDED.citation_short,
    hierarchy_path = EXCLUDED.hierarchy_path
"""

DELETE_ORPHAN_PROVISIONS = """
DELETE FROM legal_provision
WHERE doc_id = %s AND provision_key NOT IN %s
"""

DELETE_ORPHAN_CHUNKS = """
DELETE FROM legal_chunk
WHERE doc_id = %s AND chunk_id NOT IN %s
"""


def write_document(doc: LegalDocumentRow) -> dict:
    """
    Grava documento completo no Postgres (atomico).

    Args:
        doc: LegalDocumentRow com provisions e chunks preenchidos.

    Returns:
        dict com contagens: {"provisions": N, "chunks": N, "orphans_removed": N}
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. UPSERT legal_document
            cur.execute(UPSERT_DOCUMENT, (
                doc.doc_id,
                doc.jurisdiction_id,
                doc.doc_type,
                doc.number,
                doc.year,
                doc.title,
                doc.source_blob_path,
                doc.source_format,
                doc.text_sha256,
                doc.char_count,
                len(doc.provisions),
                len(doc.chunks),
                "chunked",
            ))

            # 2. UPSERT provisions
            for prov in doc.provisions:
                cur.execute(UPSERT_PROVISION, (
                    doc.doc_id,
                    prov.provision_key,
                    prov.label,
                    prov.provision_type,
                    prov.parent_key,
                    prov.hierarchy_path,
                    prov.order_in_doc,
                ))

            # 3. UPSERT chunks
            for chunk in doc.chunks:
                cur.execute(UPSERT_CHUNK, (
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.provision_key,
                    chunk.order_in_doc,
                    chunk.content,
                    chunk.content_hash,
                    chunk.char_count,
                    chunk.citation_short,
                    chunk.hierarchy_path,
                ))

            # 4. Remove orphans (provisions/chunks que nao estao mais no doc)
            orphans_removed = 0
            if doc.provisions:
                prov_keys = tuple(p.provision_key for p in doc.provisions)
                cur.execute(DELETE_ORPHAN_PROVISIONS, (doc.doc_id, prov_keys))
                orphans_removed += cur.rowcount

            if doc.chunks:
                chunk_ids = tuple(c.chunk_id for c in doc.chunks)
                cur.execute(DELETE_ORPHAN_CHUNKS, (doc.doc_id, chunk_ids))
                orphans_removed += cur.rowcount

        conn.commit()
        logger.info(
            "doc_id=%s: gravado (%d provisions, %d chunks, %d orphans removidos)",
            doc.doc_id, len(doc.provisions), len(doc.chunks), orphans_removed,
        )
        return {
            "provisions": len(doc.provisions),
            "chunks": len(doc.chunks),
            "orphans_removed": orphans_removed,
        }

    except Exception:
        conn.rollback()
        logger.exception("Erro ao gravar doc_id=%s", doc.doc_id)
        raise
    finally:
        release_conn(conn)
