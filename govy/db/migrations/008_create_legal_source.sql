-- 008_create_legal_source.sql
-- Tabela de controle para fontes de legislacao monitoradas (watchers).
-- doc_id é PK mas NÃO FK de legal_document — um item pode ser registrado
-- antes de ser ingerido com sucesso. A ligação é lógica (mesmo doc_id).

CREATE TABLE IF NOT EXISTS legal_source (
    doc_id          VARCHAR(120) PRIMARY KEY,
    kind            VARCHAR(40)  NOT NULL,
    jurisdiction    VARCHAR(20)  NOT NULL DEFAULT 'federal/BR',
    source_url      TEXT         NOT NULL,
    list_url        TEXT,
    caption_raw     TEXT,
    status_hint     VARCHAR(20)  NOT NULL DEFAULT 'vigente',
    fingerprint     VARCHAR(64),
    etag            TEXT,
    last_modified   TEXT,
    ingest_status   VARCHAR(20)  NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_kind ON legal_source (kind);
CREATE INDEX IF NOT EXISTS idx_source_status ON legal_source (ingest_status);
CREATE INDEX IF NOT EXISTS idx_source_hint ON legal_source (status_hint);
