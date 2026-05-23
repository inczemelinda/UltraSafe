ALTER TABLE template_change_suggestion
    DROP CONSTRAINT IF EXISTS template_change_suggestion_status_check;

ALTER TABLE template_change_suggestion
    ADD CONSTRAINT template_change_suggestion_status_check CHECK (
        status IN (
            'draft',
            'accepted',
            'rejected',
            'superseded',
            'applied_to_draft'
        )
    );

CREATE TABLE IF NOT EXISTS template_draft_revision (
    id UUID PRIMARY KEY,
    suggestion_id UUID NOT NULL REFERENCES template_change_suggestion(id),
    template_id BIGINT NOT NULL REFERENCES template(id),
    template_code TEXT NOT NULL,
    template_name TEXT NOT NULL,
    base_template_version TEXT NOT NULL,
    base_template_version_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'accepted', 'rejected', 'superseded')
    ),
    base_content TEXT NOT NULL,
    revised_content TEXT NOT NULL,
    applied_hunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS template_draft_revision_suggestion_idx
    ON template_draft_revision(suggestion_id);

CREATE INDEX IF NOT EXISTS template_draft_revision_template_idx
    ON template_draft_revision(template_id);

CREATE INDEX IF NOT EXISTS template_draft_revision_status_idx
    ON template_draft_revision(status);
