CREATE TABLE IF NOT EXISTS quote_acceptance (
    id BIGSERIAL PRIMARY KEY,
    quote_request_id UUID NOT NULL REFERENCES quote_request(request_id),
    quote_document_id BIGINT NOT NULL REFERENCES quote_document(id),
    accepted_by_auth_user_id BIGINT REFERENCES auth_user(id),
    accepted_by_customer_id BIGINT NOT NULL REFERENCES customer(id),
    signer_name TEXT NOT NULL,
    signer_email TEXT NOT NULL,
    signer_role TEXT,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acceptance_method TEXT NOT NULL CHECK (
        acceptance_method IN (
            'client_portal',
            'employee_recorded',
            'seed',
            'api'
        )
    ),
    ip_address TEXT,
    user_agent TEXT,
    acceptance_statement TEXT NOT NULL,
    quote_content_hash TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_acceptance_quote_request_id
    ON quote_acceptance(quote_request_id);

CREATE INDEX IF NOT EXISTS idx_quote_acceptance_quote_document_id
    ON quote_acceptance(quote_document_id);

CREATE INDEX IF NOT EXISTS idx_quote_acceptance_customer_id
    ON quote_acceptance(accepted_by_customer_id, accepted_at DESC);

ALTER TABLE contract
    ADD COLUMN IF NOT EXISTS source_quote_acceptance_id BIGINT
        REFERENCES quote_acceptance(id);

CREATE INDEX IF NOT EXISTS idx_contract_source_quote_acceptance_id
    ON contract(source_quote_acceptance_id);
