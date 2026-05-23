ALTER TABLE customer
    ADD COLUMN IF NOT EXISTS customer_profile_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customer_profile_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS customer_profile_updated_by_auth_user_id BIGINT,
    ADD COLUMN IF NOT EXISTS customer_profile_completion_source TEXT,
    ADD COLUMN IF NOT EXISTS profile_update_count INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'customer_profile_completion_source_check'
    ) THEN
        ALTER TABLE customer
            ADD CONSTRAINT customer_profile_completion_source_check
            CHECK (
                customer_profile_completion_source IN (
                    'client_self_service',
                    'employee_link',
                    'admin_update',
                    'seed'
                )
                OR customer_profile_completion_source IS NULL
            );
    END IF;
END $$;

UPDATE customer
SET customer_profile_completed_at = COALESCE(customer_profile_completed_at, NOW()),
    customer_profile_updated_at = COALESCE(customer_profile_updated_at, NOW()),
    customer_profile_completion_source = COALESCE(customer_profile_completion_source, 'seed'),
    profile_update_count = GREATEST(COALESCE(profile_update_count, 0), 1)
WHERE full_name IS NOT NULL
  AND email IS NOT NULL
  AND phone IS NOT NULL
  AND address_id IS NOT NULL;

ALTER TABLE auth_user
    DROP CONSTRAINT IF EXISTS auth_user_role_check;

ALTER TABLE auth_user
    ADD CONSTRAINT auth_user_role_check
    CHECK (role IN ('client', 'employee', 'underwriter', 'admin'));

UPDATE auth_user
SET client_id = NULL
WHERE client_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM customer
      WHERE customer.id = auth_user.client_id
  );

ALTER TABLE auth_user
    DROP CONSTRAINT IF EXISTS auth_user_client_id_fkey;

ALTER TABLE auth_user
    ADD CONSTRAINT auth_user_client_id_fkey
    FOREIGN KEY (client_id) REFERENCES customer(id);

CREATE INDEX IF NOT EXISTS idx_auth_user_client_id
    ON auth_user(client_id);
