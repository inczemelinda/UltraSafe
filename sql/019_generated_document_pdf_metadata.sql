ALTER TABLE generated_document
    ADD COLUMN IF NOT EXISTS pdf_storage_key TEXT,
    ADD COLUMN IF NOT EXISTS pdf_filename TEXT,
    ADD COLUMN IF NOT EXISTS pdf_content_hash TEXT,
    ADD COLUMN IF NOT EXISTS pdf_source_content_hash TEXT,
    ADD COLUMN IF NOT EXISTS pdf_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS pdf_generation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_generated_document_pdf_source_hash
    ON generated_document(pdf_source_content_hash);

