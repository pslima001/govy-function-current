-- 003_create_legal_provision.sql
-- Dispositivos legais (artigos, paragrafos, incisos, alineas)

CREATE TABLE IF NOT EXISTS legal_provision (
    provision_id     SERIAL        PRIMARY KEY,
    doc_id           VARCHAR(120)  NOT NULL REFERENCES legal_document(doc_id) ON DELETE CASCADE,
    provision_key    VARCHAR(80)   NOT NULL,           -- 'art_1', 'art_1_par_1', 'art_1_par_1_inc_II'
    label            VARCHAR(120)  NOT NULL,           -- 'Art. 1o', 'Par. 1o', 'Inciso II'
    provision_type   VARCHAR(30)   NOT NULL,           -- 'artigo', 'paragrafo', 'inciso', 'alinea', 'preambulo', 'anexo'
        CHECK (provision_type IN ('preambulo', 'artigo', 'paragrafo', 'inciso', 'alinea', 'caput', 'anexo', 'titulo', 'capitulo', 'secao')),
    parent_key       VARCHAR(80),                      -- provision_key do pai (ex: art_1 para art_1_par_1)
    hierarchy_path   TEXT[],                           -- ex: ARRAY['Capitulo II', 'Secao I', 'Art. 5', 'Par. 1o']
    order_in_doc     INTEGER       NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    UNIQUE (doc_id, provision_key)
);

CREATE INDEX IF NOT EXISTS idx_provision_doc ON legal_provision(doc_id);
CREATE INDEX IF NOT EXISTS idx_provision_type ON legal_provision(provision_type);
CREATE INDEX IF NOT EXISTS idx_provision_parent ON legal_provision(doc_id, parent_key);
