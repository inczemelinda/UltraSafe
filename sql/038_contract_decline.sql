ALTER TABLE contract
    DROP CONSTRAINT IF EXISTS contract_status_check,
    ADD CONSTRAINT contract_status_check
        CHECK (status IN ('draft', 'generated', 'issued', 'expired', 'declined'));

CREATE TABLE IF NOT EXISTS contract_decline (
    id BIGSERIAL PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contract(id),
    source_quote_request_id UUID REFERENCES quote_request(request_id),
    declined_by_auth_user_id BIGINT REFERENCES auth_user(id),
    declined_by_customer_id BIGINT NOT NULL REFERENCES customer(id),
    reason TEXT,
    declined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contract_decline_contract_id
    ON contract_decline(contract_id);

CREATE INDEX IF NOT EXISTS idx_contract_decline_customer_id
    ON contract_decline(declined_by_customer_id, declined_at DESC);

CREATE INDEX IF NOT EXISTS idx_contract_decline_source_quote
    ON contract_decline(source_quote_request_id);
