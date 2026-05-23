CREATE TABLE IF NOT EXISTS address (
    id BIGSERIAL PRIMARY KEY,
    country TEXT NOT NULL,
    county TEXT NOT NULL,
    city TEXT NOT NULL,
    street TEXT NOT NULL,
    number TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    full_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('individual', 'company')),
    full_name TEXT NOT NULL,
    national_id TEXT,
    company_id TEXT,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address_id BIGINT NOT NULL REFERENCES address(id),
    customer_profile_completed_at TIMESTAMPTZ,
    customer_profile_updated_at TIMESTAMPTZ,
    customer_profile_updated_by_auth_user_id BIGINT,
    customer_profile_completion_source TEXT CHECK (
        customer_profile_completion_source IN (
            'client_self_service',
            'employee_link',
            'admin_update',
            'seed'
        )
    ),
    profile_update_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS insurer (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    company_id TEXT NOT NULL,
    representative_name TEXT NOT NULL,
    representative_role TEXT NOT NULL,
    address_id BIGINT NOT NULL REFERENCES address(id)
);

CREATE TABLE IF NOT EXISTS insured_asset (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    asset_type TEXT NOT NULL,
    usage_type TEXT NOT NULL,
    construction_type TEXT NOT NULL,
    year_built INTEGER NOT NULL,
    floor INTEGER,
    area_sqm NUMERIC(10,2) NOT NULL,
    declared_value NUMERIC(14,2) NOT NULL,
    occupancy TEXT NOT NULL,
    previous_claims_count INTEGER NOT NULL DEFAULT 0,
    address_id BIGINT NOT NULL REFERENCES address(id),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS contract (
    id UUID PRIMARY KEY,
    contract_number TEXT NOT NULL UNIQUE,
    document_type TEXT NOT NULL,
    document_version TEXT NOT NULL,
    insurer_id BIGINT NOT NULL REFERENCES insurer(id),
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    insured_asset_id BIGINT NOT NULL REFERENCES insured_asset(id),
    issue_date DATE NOT NULL,
    effective_date DATE NOT NULL,
    expiration_date DATE NOT NULL,
    jurisdiction TEXT NOT NULL,
    governing_law TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'generated', 'issued', 'expired', 'declined')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_profile (
    id BIGSERIAL PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contract(id),
    overall_risk_level TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    assessment_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_factor (
    id BIGSERIAL PRIMARY KEY,
    risk_profile_id BIGINT NOT NULL REFERENCES risk_profile(id),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    level TEXT NOT NULL,
    score INTEGER NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    clause_tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    premium_adjustment_percent NUMERIC(6,2) NOT NULL DEFAULT 0,
    deductible_adjustment_ron NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pricing (
    id BIGSERIAL PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contract(id),
    base_premium_ron NUMERIC(12,2) NOT NULL,
    adjustments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    final_premium_ron NUMERIC(12,2) NOT NULL,
    payment_plan_type TEXT NOT NULL,
    installments INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS template (
    id BIGSERIAL PRIMARY KEY,
    template_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    document_type TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_document (
    id BIGSERIAL PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contract(id),
    template_id BIGINT NOT NULL REFERENCES template(id),
    generation_status TEXT NOT NULL CHECK (generation_status IN ('pending', 'success', 'failed')),
    rendered_text TEXT NOT NULL,
    rendered_json JSONB NOT NULL,
    file_url TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS case_context(
case_id UUID primary key,
status TEXT,
context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

Create table if not exists contract_request(
request_id INT primary key,
client_id INT,
request_status TEXT DEFAULT 'created',
client_data JSONB NOT NULL DEFAULT '{}'::jsonb,
insured_data JSONB NOT NULL DEFAULT '{}'::jsonb,
request_details JSONB NOT NULL DEFAULT '{}'::jsonb,
attachments JSONB NOT NULL DEFAULT '{}'::jsonb,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_user (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('client', 'employee', 'underwriter', 'admin')),
    full_name TEXT NOT NULL,
    phone TEXT,
    client_id BIGINT REFERENCES customer(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_user_client_id
    ON auth_user(client_id);

CREATE TABLE IF NOT EXISTS customer_auth_user_link_audit (
    id BIGSERIAL PRIMARY KEY,
    auth_user_id BIGINT NOT NULL REFERENCES auth_user(id),
    old_customer_id BIGINT REFERENCES customer(id),
    new_customer_id BIGINT REFERENCES customer(id),
    action TEXT NOT NULL CHECK (action IN ('link', 'unlink', 'relink')),
    reason TEXT,
    changed_by_auth_user_id BIGINT REFERENCES auth_user(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_customer_auth_user_link_audit_auth_user
    ON customer_auth_user_link_audit(auth_user_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_customer_auth_user_link_audit_old_customer
    ON customer_auth_user_link_audit(old_customer_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_customer_auth_user_link_audit_new_customer
    ON customer_auth_user_link_audit(new_customer_id, changed_at DESC);

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
