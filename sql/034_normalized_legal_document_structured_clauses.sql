ALTER TABLE normalized_legal_document
    ADD COLUMN IF NOT EXISTS instrument_date DATE;

ALTER TABLE normalized_legal_document
    ADD COLUMN IF NOT EXISTS structured_clauses JSONB NOT NULL DEFAULT '[]'::jsonb;
