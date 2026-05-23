-- Enforce the post-conversion lifecycle rule:
-- one converted quote_request maps to one contract, and every contract must
-- carry exactly one source_quote_request_id. This does not require draft,
-- rejected, failed, or otherwise unconverted quote_request rows to have a
-- contract.

BEGIN;

-- Backfill known demo contracts created before the quote-to-contract lifecycle
-- columns existed. This is intentionally limited to deterministic demo policy
-- numbers; production-like orphan contracts are rejected below instead of
-- silently linked to invented quotes.
WITH demo_contract_quotes (
    contract_number,
    source_quote_request_id,
    request_status
) AS (
    VALUES
    ('PAD-RISK-2026-000145', '11111111-1111-4111-8111-000000000001'::uuid, 'approved'),
    ('PAD-PROPERTY-2026-000150', '11111111-1111-4111-8111-000000000005'::uuid, 'auto_accepted'),
    ('PAD-MARIA-2026-000201', '33333333-3333-4333-8333-000000000101'::uuid, 'approved'),
    ('PAD-ANDREI-2026-000202', '33333333-3333-4333-8333-000000000102'::uuid, 'auto_accepted'),
    ('PAD-IOANA-2026-000203', '33333333-3333-4333-8333-000000000103'::uuid, 'approved'),
    ('PAD-CARPATICA-2026-000204', '33333333-3333-4333-8333-000000000104'::uuid, 'approved')
),
demo_sources AS (
    SELECT
        contract.id AS contract_id,
        contract.contract_number,
        demo_contract_quotes.source_quote_request_id,
        demo_contract_quotes.request_status,
        contract.customer_id,
        jsonb_build_object(
            'type', customer.type,
            'full_name', customer.full_name,
            'national_id', customer.national_id,
            'company_id', customer.company_id,
            'email', customer.email,
            'phone', customer.phone,
            'address', customer_address.full_text
        ) AS client_data,
        jsonb_build_object(
            'asset_type', asset.asset_type,
            'usage_type', asset.usage_type,
            'construction_type', asset.construction_type,
            'year_built', asset.year_built,
            'floor', asset.floor,
            'area_sqm', asset.area_sqm,
            'declared_value', asset.declared_value,
            'occupancy', asset.occupancy,
            'previous_claims_count', asset.previous_claims_count,
            'address', jsonb_build_object(
                'country', asset_address.country,
                'county', asset_address.county,
                'city', asset_address.city,
                'street', asset_address.street,
                'number', asset_address.number,
                'postal_code', asset_address.postal_code,
                'full_text', asset_address.full_text
            )
        ) AS asset_data,
        jsonb_build_object(
            'request_details', jsonb_build_object(
                'coverage_amount', asset.declared_value,
                'security_features', jsonb_build_array()
            ),
            'pricing', jsonb_build_object(
                'final_premium', COALESCE(pricing.final_premium_ron, 0),
                'base_premium', COALESCE(pricing.base_premium_ron, pricing.final_premium_ron, 0)
            )
        ) AS pricing_preview
    FROM demo_contract_quotes
    JOIN contract ON contract.contract_number = demo_contract_quotes.contract_number
    JOIN customer ON customer.id = contract.customer_id
    JOIN address customer_address ON customer_address.id = customer.address_id
    JOIN insured_asset asset ON asset.id = contract.insured_asset_id
    JOIN address asset_address ON asset_address.id = asset.address_id
    LEFT JOIN LATERAL (
        SELECT *
        FROM pricing
        WHERE pricing.contract_id = contract.id
        ORDER BY pricing.id DESC
        LIMIT 1
    ) pricing ON TRUE
    WHERE contract.source_quote_request_id IS NULL
)
INSERT INTO quote_request (
    request_id,
    client_id,
    request_status,
    client_data,
    asset_data,
    quote_steps,
    mandatory_data_status,
    attachments,
    pricing_preview,
    created_at,
    updated_at
)
SELECT
    source_quote_request_id,
    customer_id,
    request_status,
    client_data,
    asset_data,
    '[{"step":"migration","value":"Backfilled deterministic demo quote source for one-to-one contract provenance."}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    pricing_preview,
    NOW(),
    NOW()
FROM demo_sources
ON CONFLICT (request_id) DO UPDATE SET
    client_id = EXCLUDED.client_id,
    request_status = EXCLUDED.request_status,
    client_data = EXCLUDED.client_data,
    asset_data = EXCLUDED.asset_data,
    mandatory_data_status = EXCLUDED.mandatory_data_status,
    pricing_preview = EXCLUDED.pricing_preview,
    updated_at = NOW();

WITH demo_contract_quotes (
    contract_number,
    source_quote_request_id
) AS (
    VALUES
    ('PAD-RISK-2026-000145', '11111111-1111-4111-8111-000000000001'::uuid),
    ('PAD-PROPERTY-2026-000150', '11111111-1111-4111-8111-000000000005'::uuid),
    ('PAD-MARIA-2026-000201', '33333333-3333-4333-8333-000000000101'::uuid),
    ('PAD-ANDREI-2026-000202', '33333333-3333-4333-8333-000000000102'::uuid),
    ('PAD-IOANA-2026-000203', '33333333-3333-4333-8333-000000000103'::uuid),
    ('PAD-CARPATICA-2026-000204', '33333333-3333-4333-8333-000000000104'::uuid)
)
UPDATE contract
SET source_quote_request_id = demo_contract_quotes.source_quote_request_id,
    updated_at = NOW()
FROM demo_contract_quotes
WHERE contract.contract_number = demo_contract_quotes.contract_number
  AND contract.source_quote_request_id IS NULL;

DO $$
DECLARE
    orphan_contract_count integer;
    duplicate_source_count integer;
    missing_document_count integer;
    mismatched_document_count integer;
BEGIN
    SELECT COUNT(*)
    INTO orphan_contract_count
    FROM contract
    WHERE source_quote_request_id IS NULL;

    IF orphan_contract_count > 0 THEN
        RAISE EXCEPTION
            'Cannot enforce one converted quote to one contract: % contract rows have no source_quote_request_id. Run the validation query for contracts without quote provenance and backfill or archive those rows before applying this migration.',
            orphan_contract_count;
    END IF;

    SELECT COUNT(*)
    INTO duplicate_source_count
    FROM (
        SELECT source_quote_request_id
        FROM contract
        WHERE source_quote_request_id IS NOT NULL
        GROUP BY source_quote_request_id
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_source_count > 0 THEN
        RAISE EXCEPTION
            'Cannot enforce one converted quote to one contract: % source_quote_request_id values are linked to multiple contracts. Resolve duplicate converted quote links before applying this migration.',
            duplicate_source_count;
    END IF;

    SELECT COUNT(*)
    INTO missing_document_count
    FROM contract c
    LEFT JOIN quote_document qd ON qd.id = c.source_quote_document_id
    WHERE c.source_quote_document_id IS NOT NULL
      AND qd.id IS NULL;

    IF missing_document_count > 0 THEN
        RAISE EXCEPTION
            'Cannot enforce source quote document integrity: % contracts reference a missing source_quote_document_id.',
            missing_document_count;
    END IF;

    SELECT COUNT(*)
    INTO mismatched_document_count
    FROM contract c
    JOIN quote_document qd ON qd.id = c.source_quote_document_id
    WHERE c.source_quote_document_id IS NOT NULL
      AND qd.quote_request_id <> c.source_quote_request_id;

    IF mismatched_document_count > 0 THEN
        RAISE EXCEPTION
            'Cannot enforce source quote document integrity: % contracts reference a quote_document that belongs to a different quote_request.',
            mismatched_document_count;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_contract_source_quote_request_id
    ON contract(source_quote_request_id);

ALTER TABLE contract
    ALTER COLUMN source_quote_request_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_quote_document_id_quote_request'
    ) THEN
        ALTER TABLE quote_document
            ADD CONSTRAINT uq_quote_document_id_quote_request
            UNIQUE (id, quote_request_id);
    END IF;
END $$;

ALTER TABLE contract
    DROP CONSTRAINT IF EXISTS fk_contract_source_quote_document_request;

ALTER TABLE contract
    ADD CONSTRAINT fk_contract_source_quote_document_request
    FOREIGN KEY (source_quote_document_id, source_quote_request_id)
    REFERENCES quote_document(id, quote_request_id);

-- Validation queries for operators:
-- Contracts without quote provenance, migration blocker:
-- SELECT id, contract_number FROM contract WHERE source_quote_request_id IS NULL;
--
-- Duplicate quote-to-contract links, migration blocker:
-- SELECT source_quote_request_id, COUNT(*)
-- FROM contract
-- WHERE source_quote_request_id IS NOT NULL
-- GROUP BY source_quote_request_id
-- HAVING COUNT(*) > 1;
--
-- Contract linked to a quote document from a different quote, migration blocker:
-- SELECT c.id, c.source_quote_request_id, qd.quote_request_id
-- FROM contract c
-- JOIN quote_document qd ON qd.id = c.source_quote_document_id
-- WHERE qd.quote_request_id <> c.source_quote_request_id;
--
-- Contract linked to a missing quote document, migration blocker:
-- SELECT c.id, c.source_quote_document_id
-- FROM contract c
-- LEFT JOIN quote_document qd ON qd.id = c.source_quote_document_id
-- WHERE c.source_quote_document_id IS NOT NULL
--   AND qd.id IS NULL;
--
-- Quotes with no contract, informational only:
-- SELECT qr.request_id, qr.request_status
-- FROM quote_request qr
-- LEFT JOIN contract c ON c.source_quote_request_id = qr.request_id
-- WHERE c.id IS NULL;

COMMIT;
