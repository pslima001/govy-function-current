-- 001_create_jurisdiction.sql
-- Tabela de jurisdicoes (BR federal + 27 UFs)

CREATE TABLE IF NOT EXISTS jurisdiction (
    jurisdiction_id  VARCHAR(20)  PRIMARY KEY,   -- ex: 'federal_br', 'sp', 'mg'
    name             VARCHAR(120) NOT NULL,       -- ex: 'Federal - Brasil'
    uf               VARCHAR(2),                  -- NULL para federal
    level            VARCHAR(20)  NOT NULL        -- 'federal' | 'estadual' | 'municipal'
        CHECK (level IN ('federal', 'estadual', 'municipal')),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
