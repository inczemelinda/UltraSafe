CREATE TABLE IF NOT EXISTS claim_request (
    request_id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    request_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (request_status IN (
            'draft',
            'submitted',
            'screening',
            'needs_underwriter_review',
            'coverage_review_required',
            'in_review',
            'completed',
            'failed'
        )),
    client_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    claim_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claim_request_client_id
    ON claim_request(client_id);

CREATE INDEX IF NOT EXISTS idx_claim_request_status
    ON claim_request(request_status);

CREATE INDEX IF NOT EXISTS idx_claim_request_created_at
    ON claim_request(created_at DESC);
