ALTER TABLE generated_document
    ADD COLUMN IF NOT EXISTS template_code TEXT,
    ADD COLUMN IF NOT EXISTS template_version TEXT,
    ADD COLUMN IF NOT EXISTS template_version_hash TEXT,
    ADD COLUMN IF NOT EXISTS payload_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS generation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_generated_document_contract_created_at
    ON generated_document(contract_id, created_at DESC);

