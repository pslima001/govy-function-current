-- 007_add_vigencia_fields.sql
-- Adiciona campos de vigencia e publicacao ao legal_document e legal_provision.
-- Tambem enriquece legal_relation com evidence/confidence.

-- legal_document: datas e status de vigencia
ALTER TABLE legal_document
    ADD COLUMN IF NOT EXISTS published_at      DATE,
    ADD COLUMN IF NOT EXISTS effective_from     DATE,
    ADD COLUMN IF NOT EXISTS effective_to       DATE,
    ADD COLUMN IF NOT EXISTS status_vigencia    VARCHAR(30) DEFAULT 'desconhecido'
        CHECK (status_vigencia IN (
            'vigente', 'revogada', 'parcialmente_revogada',
            'desconhecido', 'eficacia_condicionada', 'vacatio'
        ));

-- legal_provision: vigencia por dispositivo (para revogacao parcial)
ALTER TABLE legal_provision
    ADD COLUMN IF NOT EXISTS valid_from         DATE,
    ADD COLUMN IF NOT EXISTS valid_to           DATE,
    ADD COLUMN IF NOT EXISTS status_vigencia    VARCHAR(30) DEFAULT 'vigente'
        CHECK (status_vigencia IN (
            'vigente', 'revogada', 'alterada', 'desconhecido'
        ));

-- legal_relation: enriquecer com evidence
ALTER TABLE legal_relation
    ADD COLUMN IF NOT EXISTS confidence         VARCHAR(10) DEFAULT 'low'
        CHECK (confidence IN ('high', 'medium', 'low')),
    ADD COLUMN IF NOT EXISTS needs_review       BOOLEAN DEFAULT true,
    ADD COLUMN IF NOT EXISTS evidence_text      TEXT,
    ADD COLUMN IF NOT EXISTS evidence_pattern   VARCHAR(200),
    ADD COLUMN IF NOT EXISTS evidence_position  INTEGER;

-- Indices para consultas de vigencia
CREATE INDEX IF NOT EXISTS idx_legal_doc_vigencia ON legal_document(status_vigencia);
CREATE INDEX IF NOT EXISTS idx_legal_doc_effective ON legal_document(effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_relation_confidence ON legal_relation(confidence, needs_review);
