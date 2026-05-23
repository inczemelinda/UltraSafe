ALTER TABLE contract
    ADD COLUMN IF NOT EXISTS source_quote_request_id UUID
        REFERENCES quote_request(request_id),
    ADD COLUMN IF NOT EXISTS source_quote_document_id BIGINT
        REFERENCES quote_document(id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contract_source_quote_request_id
    ON contract(source_quote_request_id);

CREATE INDEX IF NOT EXISTS idx_contract_source_quote_document_id
    ON contract(source_quote_document_id);

