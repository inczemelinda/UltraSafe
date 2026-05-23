CREATE TABLE IF NOT EXISTS legal_document_template_review_candidate (
    candidate_id UUID PRIMARY KEY,
    normalized_legal_document_id UUID NOT NULL REFERENCES normalized_legal_document(id),
    template_id BIGINT NOT NULL REFERENCES template(id),
    template_code TEXT NOT NULL,
    template_name TEXT NOT NULL,
    template_version TEXT NOT NULL,
    template_version_hash TEXT NOT NULL,
    match_type TEXT NOT NULL CHECK (
        match_type IN (
            'amended_reference',
            'repealed_reference',
            'direct_reference',
            'keyword_topic'
        )
    ),
    matched_reference TEXT,
    review_reason TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'needs_review' CHECK (
        status IN ('needs_review', 'accepted', 'dismissed')
    ),
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        normalized_legal_document_id,
        template_id,
        template_version_hash,
        match_type,
        matched_reference
    )
);

CREATE INDEX IF NOT EXISTS legal_document_template_review_candidate_status_idx
    ON legal_document_template_review_candidate(status);

CREATE INDEX IF NOT EXISTS legal_document_template_review_candidate_demo_dataset_idx
    ON legal_document_template_review_candidate ((source_metadata->>'demo_dataset'));
