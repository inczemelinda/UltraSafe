CREATE TABLE IF NOT EXISTS normalized_legal_document (
    id UUID PRIMARY KEY,
    raw_source_item_id UUID NOT NULL REFERENCES raw_source_item(raw_item_id),
    source_id TEXT NOT NULL REFERENCES intelligence_source(source_id),
    source_key TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    parser_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    external_identifier TEXT,
    title TEXT NOT NULL,
    language TEXT,
    issuer TEXT,
    instrument_type TEXT,
    instrument_number TEXT,
    instrument_year INTEGER,
    instrument_date DATE,
    publication_reference TEXT,
    publication_date DATE,
    effective_date DATE,
    status TEXT,
    legal_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    structured_clauses JSONB NOT NULL DEFAULT '[]'::jsonb,
    amends JSONB NOT NULL DEFAULT '[]'::jsonb,
    repeals JSONB NOT NULL DEFAULT '[]'::jsonb,
    full_text TEXT NOT NULL,
    summary TEXT,
    document_hash TEXT NOT NULL,
    extraction_confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    parser_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_source_item_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS normalized_legal_document_external_identifier_key
    ON normalized_legal_document(source_id, external_identifier)
    WHERE external_identifier IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS normalized_legal_document_canonical_url_key
    ON normalized_legal_document(source_id, canonical_url);

CREATE UNIQUE INDEX IF NOT EXISTS normalized_legal_document_document_hash_key
    ON normalized_legal_document(source_id, document_hash);

CREATE INDEX IF NOT EXISTS normalized_legal_document_source_key_idx
    ON normalized_legal_document(source_id, source_key);

CREATE TABLE IF NOT EXISTS legal_document_normalization_result (
    id UUID PRIMARY KEY,
    raw_source_item_id UUID NOT NULL REFERENCES raw_source_item(raw_item_id),
    source_id TEXT NOT NULL REFERENCES intelligence_source(source_id),
    parser_id TEXT NOT NULL,
    normalized_legal_document_id UUID REFERENCES normalized_legal_document(id),
    status TEXT NOT NULL CHECK (
        status IN (
            'normalized',
            'parser_failed',
            'suppressed_non_legislative',
            'duplicate_unchanged',
            'skipped_missing_required_fields'
        )
    ),
    reason TEXT,
    parser_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_source_item_id)
);

CREATE INDEX IF NOT EXISTS legal_document_normalization_result_status_idx
    ON legal_document_normalization_result(source_id, status);
