CREATE TABLE IF NOT EXISTS quote_document (
    id BIGSERIAL PRIMARY KEY,
    quote_request_id UUID NOT NULL REFERENCES quote_request(request_id) ON DELETE CASCADE,
    template_id BIGINT NOT NULL REFERENCES template(id),
    generation_status TEXT NOT NULL
        CHECK (generation_status IN ('pending', 'success', 'failed')),
    rendered_text TEXT NOT NULL,
    rendered_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    file_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quote_document_quote_request_id
    ON quote_document(quote_request_id);

CREATE INDEX IF NOT EXISTS idx_quote_document_created_at
    ON quote_document(created_at DESC);
