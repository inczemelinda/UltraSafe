CREATE TABLE IF NOT EXISTS quote_decision_audit (
    id BIGSERIAL PRIMARY KEY,
    quote_request_id UUID NOT NULL REFERENCES quote_request(request_id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    decision_status TEXT NOT NULL CHECK (decision_status IN (
        'approved',
        'disapproved',
        'field_review_required'
    )),
    reason TEXT,
    decided_by_auth_user_id BIGINT,
    decided_by_name TEXT,
    decided_by_email TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_quote_decision_audit_quote_request
    ON quote_decision_audit(quote_request_id, decided_at DESC, id DESC);
