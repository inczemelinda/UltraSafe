CREATE TABLE IF NOT EXISTS quote_request (
    request_id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    request_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (request_status IN (
            'draft',
            'pricing_in_progress',
            'quote_ready',
            'auto_accepted',
            'underwriter_review',
            'approved',
            'disapproved',
            'field_review_required',
            'failed'
        )),

    client_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    asset_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    quote_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    mandatory_data_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    pricing_preview JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quote_request_client_id
    ON quote_request(client_id);

CREATE INDEX IF NOT EXISTS idx_quote_request_status
    ON quote_request(request_status);

CREATE INDEX IF NOT EXISTS idx_quote_request_created_at
    ON quote_request(created_at DESC);