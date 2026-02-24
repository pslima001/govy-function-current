-- 005_create_legal_relation.sql
-- Relacoes entre documentos legais (revoga, altera, regulamenta, etc.)

CREATE TABLE IF NOT EXISTS legal_relation (
    relation_id      SERIAL        PRIMARY KEY,
    source_doc_id    VARCHAR(120)  NOT NULL REFERENCES legal_document(doc_id) ON DELETE CASCADE,
    target_doc_id    VARCHAR(120)  REFERENCES legal_document(doc_id) ON DELETE SET NULL,
    target_ref       TEXT,                             -- referencia textual se target nao esta no DB
    relation_type    VARCHAR(30)   NOT NULL
        CHECK (relation_type IN ('revoga', 'altera', 'regulamenta', 'complementa', 'referencia')),
    source_provision VARCHAR(80),                      -- provision_key especifico (opcional)
    notes            TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    UNIQUE (source_doc_id, target_doc_id, relation_type, source_provision)
);

CREATE INDEX IF NOT EXISTS idx_relation_source ON legal_relation(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON legal_relation(target_doc_id);
