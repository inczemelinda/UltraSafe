CREATE TABLE IF NOT EXISTS intelligence_source (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    source_type TEXT NOT NULL,
    trust_tier TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    language TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_successful_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_source_item (
    raw_item_id UUID PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES intelligence_source(source_id),
    original_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    raw_html TEXT,
    extracted_text TEXT NOT NULL,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash TEXT NOT NULL,
    fetch_status TEXT NOT NULL DEFAULT 'success',
    parse_status TEXT NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, canonical_url),
    UNIQUE (source_id, content_hash)
);

CREATE TABLE IF NOT EXISTS external_event (
    event_id UUID PRIMARY KEY,
    raw_item_id UUID NOT NULL REFERENCES raw_source_item(raw_item_id),
    source_id TEXT NOT NULL REFERENCES intelligence_source(source_id),
    source_type TEXT NOT NULL,
    trust_tier TEXT NOT NULL,
    original_url TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    body_text_ref TEXT,
    body_text TEXT NOT NULL,
    original_language TEXT NOT NULL,
    country TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'not_relevant',
    line_of_business TEXT,
    product TEXT,
    topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    perils_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    severity TEXT NOT NULL DEFAULT 'low',
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    underwriter_summary TEXT NOT NULL DEFAULT '',
    recommended_action TEXT NOT NULL DEFAULT '',
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    classification_json JSONB,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_item_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS external_event_raw_item_id_key
    ON external_event(raw_item_id);

CREATE TABLE IF NOT EXISTS document_asset (
    document_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    country TEXT NOT NULL,
    line_of_business TEXT NOT NULL,
    product TEXT NOT NULL,
    topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner TEXT NOT NULL,
    last_reviewed_at TIMESTAMPTZ,
    review_status TEXT NOT NULL DEFAULT 'current',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS underwriting_work_item (
    work_item_id UUID PRIMARY KEY,
    type TEXT NOT NULL,
    account_name TEXT NOT NULL,
    country TEXT NOT NULL,
    county TEXT NOT NULL,
    city TEXT NOT NULL,
    line_of_business TEXT NOT NULL,
    product TEXT NOT NULL,
    insured_value NUMERIC(14,2),
    perils_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    renewal_date DATE NOT NULL,
    assigned_underwriter TEXT NOT NULL,
    status TEXT NOT NULL,
    source_ref_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence_correlation (
    correlation_id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES external_event(event_id),
    target_type TEXT NOT NULL CHECK (target_type IN ('document_asset', 'underwriting_work_item')),
    target_id UUID NOT NULL,
    rule_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    match_score NUMERIC(4,3) NOT NULL DEFAULT 0,
    llm_rank INTEGER,
    rationale TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS intelligence_alert (
    alert_id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES external_event(event_id),
    work_item_id UUID NOT NULL REFERENCES underwriting_work_item(work_item_id),
    assigned_underwriter TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, work_item_id)
);

CREATE TABLE IF NOT EXISTS intelligence_feedback (
    feedback_id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id UUID NOT NULL,
    feedback_type TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence_audit_record (
    audit_id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    raw_url TEXT,
    raw_item_id UUID,
    model_name TEXT,
    model_version TEXT,
    prompt_version TEXT,
    input_ref_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    rules_triggered_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence_ingestion_run (
    run_id UUID PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES intelligence_source(source_id),
    status TEXT NOT NULL,
    raw_items_seen INTEGER NOT NULL DEFAULT 0,
    raw_items_created INTEGER NOT NULL DEFAULT 0,
    events_created INTEGER NOT NULL DEFAULT 0,
    alerts_created INTEGER NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ
);
