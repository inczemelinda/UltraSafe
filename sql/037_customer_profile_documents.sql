CREATE TABLE IF NOT EXISTS customer_profile_document (
    id UUID PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    document_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_key TEXT NOT NULL,
    file_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_customer_profile_document_customer
    ON customer_profile_document(customer_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_profile_document_active_label
    ON customer_profile_document(customer_id, label)
    WHERE deleted_at IS NULL;
