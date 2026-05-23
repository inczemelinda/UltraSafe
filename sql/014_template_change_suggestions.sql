CREATE TABLE IF NOT EXISTS template_change_suggestion (
    id UUID PRIMARY KEY,
    candidate_id UUID NOT NULL REFERENCES legal_document_template_review_candidate(candidate_id),
    template_id BIGINT NOT NULL REFERENCES template(id),
    normalized_legal_document_id UUID NOT NULL REFERENCES normalized_legal_document(id),
    template_version_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'accepted', 'rejected', 'superseded')
    ),
    overall_summary TEXT NOT NULL,
    validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_change_suggestion_hunk (
    id UUID PRIMARY KEY,
    suggestion_id UUID NOT NULL REFERENCES template_change_suggestion(id) ON DELETE CASCADE,
    section_id TEXT,
    section_label TEXT,
    change_type TEXT NOT NULL CHECK (
        change_type IN (
            'replace',
            'insert_before',
            'insert_after',
            'delete',
            'manual_review'
        )
    ),
    old_text TEXT NOT NULL,
    new_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'accepted', 'rejected', 'edited')
    ),
    reviewer_notes TEXT
);

CREATE INDEX IF NOT EXISTS template_change_suggestion_candidate_idx
    ON template_change_suggestion(candidate_id);

CREATE INDEX IF NOT EXISTS template_change_suggestion_status_idx
    ON template_change_suggestion(status);

CREATE INDEX IF NOT EXISTS template_change_suggestion_hunk_suggestion_idx
    ON template_change_suggestion_hunk(suggestion_id);
