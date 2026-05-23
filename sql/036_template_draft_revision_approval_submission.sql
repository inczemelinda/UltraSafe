ALTER TABLE template_draft_revision
    DROP CONSTRAINT IF EXISTS template_draft_revision_status_check;

ALTER TABLE template_draft_revision
    ADD CONSTRAINT template_draft_revision_status_check CHECK (
        status IN (
            'draft',
            'submitted_for_approval',
            'accepted',
            'rejected',
            'superseded'
        )
    );
