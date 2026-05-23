CREATE TABLE IF NOT EXISTS intelligence_template_review_candidate (
    candidate_id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES external_event(event_id),
    template_id BIGINT NOT NULL REFERENCES template(id),
    template_code TEXT NOT NULL,
    template_name TEXT NOT NULL,
    template_version TEXT NOT NULL,
    event_title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    legal_references_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    rule_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    match_score NUMERIC(4,3) NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, template_id)
);
