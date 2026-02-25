-- 009_legal_source_tracking.sql
-- Adiciona campos de tracking para o timer trigger legal_watch.
-- last_success_at: timestamp do ultimo ingest bem-sucedido
-- last_error_reason: mensagem do ultimo erro (separado de error_message que e do ciclo atual)

ALTER TABLE legal_source
    ADD COLUMN IF NOT EXISTS last_success_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error_reason  TEXT;
