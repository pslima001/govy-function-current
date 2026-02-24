-- 002_create_legal_document.sql
-- Registro de documentos legais (leis, decretos, INs, etc.)

CREATE TABLE IF NOT EXISTS legal_document (
    doc_id           VARCHAR(120)  PRIMARY KEY,       -- ex: 'lei_14133_2021_federal_br'
    jurisdiction_id  VARCHAR(20)   NOT NULL REFERENCES jurisdiction(jurisdiction_id),
    doc_type         VARCHAR(40)   NOT NULL,           -- 'lei', 'decreto', 'instrucao_normativa', 'lei_complementar', etc.
    number           VARCHAR(40),                      -- '14133', '62', etc.
    year             SMALLINT,
    title            TEXT          NOT NULL,            -- titulo completo
    source_blob_path TEXT,                             -- path no blob storage
    source_format    VARCHAR(10)   NOT NULL DEFAULT 'pdf',  -- 'pdf' | 'docx'
    text_sha256      VARCHAR(64),                      -- hash do texto extraido
    char_count       INTEGER,
    provision_count  INTEGER       DEFAULT 0,
    chunk_count      INTEGER       DEFAULT 0,
    status           VARCHAR(20)   NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'extracted', 'chunked', 'error')),
    error_message    TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_legal_doc_jurisdiction ON legal_document(jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_legal_doc_type ON legal_document(doc_type);
CREATE INDEX IF NOT EXISTS idx_legal_doc_status ON legal_document(status);
