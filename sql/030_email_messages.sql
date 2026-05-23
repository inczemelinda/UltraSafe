CREATE TABLE IF NOT EXISTS email_messages (
    id UUID PRIMARY KEY,
    case_id UUID,
    request_id UUID,
    direction TEXT NOT NULL CHECK (direction IN ('OUTBOUND', 'INBOUND')),
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'SENT', 'FAILED', 'RECEIVED')),
    provider_message_id TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_email_messages_case_id
    ON email_messages(case_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_email_messages_provider_message_id
    ON email_messages(provider_message_id);

CREATE TABLE IF NOT EXISTS email_templates (
    id UUID PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
