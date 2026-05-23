ALTER TABLE template
    ADD COLUMN IF NOT EXISTS jurisdiction TEXT,
    ADD COLUMN IF NOT EXISTS product_line TEXT,
    ADD COLUMN IF NOT EXISTS legal_references_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS template_demo_dataset_idx
    ON template ((metadata_json->>'demo_dataset'));

CREATE INDEX IF NOT EXISTS template_legal_references_idx
    ON template USING GIN (legal_references_json);

ALTER TABLE intelligence_template_review_candidate
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS intelligence_template_review_candidate_demo_dataset_idx
    ON intelligence_template_review_candidate ((metadata_json->>'demo_dataset'));
