ALTER TABLE claim_request
    DROP CONSTRAINT IF EXISTS claim_request_request_status_check;

ALTER TABLE claim_request
    ADD CONSTRAINT claim_request_request_status_check
    CHECK (request_status IN (
        'draft',
        'submitted',
        'screening',
        'needs_underwriter_review',
        'coverage_review_required',
        'in_review',
        'completed',
        'failed'
    ));
