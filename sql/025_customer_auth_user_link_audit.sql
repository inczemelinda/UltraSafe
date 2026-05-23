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
