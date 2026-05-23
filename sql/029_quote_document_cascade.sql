ALTER TABLE quote_document
    DROP CONSTRAINT IF EXISTS quote_document_quote_request_id_fkey;

ALTER TABLE quote_document
    ADD CONSTRAINT quote_document_quote_request_id_fkey
    FOREIGN KEY (quote_request_id)
    REFERENCES quote_request(request_id)
    ON DELETE CASCADE;