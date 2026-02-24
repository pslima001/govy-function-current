-- 004_create_legal_chunk.sql
-- Chunks de texto para busca e consulta

CREATE TABLE IF NOT EXISTS legal_chunk (
    chunk_id         VARCHAR(120)  PRIMARY KEY,        -- ex: 'lei_14133_2021_federal_br__art_1__0'
    doc_id           VARCHAR(120)  NOT NULL REFERENCES legal_document(doc_id) ON DELETE CASCADE,
    provision_key    VARCHAR(80)   NOT NULL,            -- link para legal_provision
    order_in_doc     INTEGER       NOT NULL DEFAULT 0,
    content          TEXT          NOT NULL,
    content_hash     VARCHAR(64)   NOT NULL,            -- sha256 do content
    char_count       INTEGER       NOT NULL,
    citation_short   VARCHAR(200),                     -- 'Lei 14.133/2021, Art. 5, Par. 1o'
    hierarchy_path   TEXT[],                           -- ex: ARRAY['Capitulo II', 'Secao I', 'Art. 5']
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunk_doc ON legal_chunk(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunk_provision ON legal_chunk(doc_id, provision_key);
CREATE INDEX IF NOT EXISTS idx_chunk_hash ON legal_chunk(content_hash);
