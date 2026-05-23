CREATE TABLE IF NOT EXISTS underwriting_rules_document (
    document_key TEXT PRIMARY KEY,
    content_json JSONB NOT NULL,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
