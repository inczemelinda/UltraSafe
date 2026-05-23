BEGIN;

DELETE FROM generated_document
WHERE id BETWEEN 1001 AND 1299;

-- Contracts now require source_quote_request_id. Only detach fixed demo quote
-- document rows before upserting them again; do not remove quote provenance.
UPDATE contract
SET source_quote_document_id = NULL,
    source_quote_acceptance_id = NULL
WHERE source_quote_document_id IN (1001, 1002, 1003, 1101, 1102, 1103, 1104)
   OR source_quote_document_id BETWEEN 1201 AND 1299
   OR source_quote_acceptance_id BETWEEN 1001 AND 1299;

DELETE FROM quote_acceptance
WHERE id BETWEEN 1001 AND 1299
   OR quote_document_id BETWEEN 1001 AND 1299;

DELETE FROM quote_document
WHERE id BETWEEN 1001 AND 1299;

DELETE FROM claim_request;

CREATE OR REPLACE FUNCTION pg_temp.demo_seed_uuid(seed_text text)
RETURNS uuid
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT (
        substr(md5(seed_text), 1, 8) || '-' ||
        substr(md5(seed_text), 9, 4) || '-' ||
        substr(md5(seed_text), 13, 4) || '-' ||
        substr(md5(seed_text), 17, 4) || '-' ||
        substr(md5(seed_text), 21, 12)
    )::uuid
$$;

CREATE OR REPLACE FUNCTION pg_temp.demo_claim_attachment(
    claim_request_id uuid,
    file_name text,
    label text,
    document_role text,
    content_type text,
    size_bytes bigint,
    policy_number text,
    claim_type text,
    estimated_damage numeric,
    summary text
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_build_object(
        'file_name', file_name,
        'content_type', content_type,
        'size_bytes', size_bytes,
        'file_url',
            '/claims/' || claim_request_id::text || '/attachments/' ||
            pg_temp.demo_seed_uuid('claim-attachment:' || claim_request_id::text || ':' || file_name)::text,
        'metadata', jsonb_build_object(
            'label', label,
            'attachment_id', pg_temp.demo_seed_uuid('claim-attachment:' || claim_request_id::text || ':' || file_name)::text,
            'storage_key', md5('claim:' || claim_request_id::text || ':' || file_name),
            'document_role', document_role,
            'source', 'demo_seed',
            'extraction_status', 'completed',
            'extraction_error', NULL,
            'extraction_summary_error', NULL,
            'extraction_summary_path', 'claim_data.attachment_extraction_summary.summary',
            'extracted_text_source', 'demo_seed',
            'extracted_at', NOW()::text,
            'extracted_text', array_to_string(ARRAY[
                '- Policy number: ' || policy_number,
                '- Claim number: ' || claim_request_id::text,
                '- Claim type: ' || claim_type,
                '- Amount: ' || estimated_damage::text || ' RON',
                '- Summary: ' || summary
            ], chr(10))
        )
    )
$$;

WITH demo_addresses (
    country,
    county,
    city,
    street,
    number,
    postal_code,
    full_text
) AS (
    VALUES
    ('Romania', 'Bucuresti', 'Bucuresti', 'Str. Ficusului', '18', '013975', 'Str. Ficusului 18, Sector 1, Bucuresti'),
    ('Romania', 'Cluj', 'Cluj-Napoca', 'Str. Observatorului', '42', '400363', 'Str. Observatorului 42, Cluj-Napoca'),
    ('Romania', 'Iasi', 'Iasi', 'Str. Pacurari', '91', '700511', 'Str. Pacurari 91, Iasi'),
    ('Romania', 'Timis', 'Timisoara', 'Bd. Take Ionescu', '27', '300062', 'Bd. Take Ionescu 27, Timisoara'),
    ('Romania', 'Brasov', 'Brasov', 'Str. Republicii', '15', '500030', 'Str. Republicii 15, Brasov'),
    ('Romania', 'Constanta', 'Constanta', 'Bd. Mamaia', '121', '900527', 'Bd. Mamaia 121, Constanta'),
    ('Romania', 'Sibiu', 'Sibiu', 'Str. Mitropoliei', '6', '550179', 'Str. Mitropoliei 6, Sibiu'),
    ('Romania', 'Prahova', 'Ploiesti', 'Str. Democratiei', '33', '100559', 'Str. Democratiei 33, Ploiesti'),
    ('Romania', 'Bihor', 'Oradea', 'Calea Aradului', '54', '410223', 'Calea Aradului 54, Oradea'),
    ('Romania', 'Bucuresti', 'Bucuresti', 'Str. Demo Claims', '1', '010001', 'Str. Demo Claims 1, Bucuresti')
)
INSERT INTO address (
    country,
    county,
    city,
    street,
    number,
    postal_code,
    full_text
)
SELECT
    country,
    county,
    city,
    street,
    number,
    postal_code,
    full_text
FROM demo_addresses
WHERE NOT EXISTS (
    SELECT 1 FROM address WHERE address.full_text = demo_addresses.full_text
);

WITH demo_customers (
    type,
    full_name,
    national_id,
    company_id,
    email,
    phone,
    address_full_text,
    completed,
    updated_days_ago,
    profile_update_count
) AS (
    VALUES
    ('individual', 'Mihai Ionescu', '2860315123456', NULL, 'mihai.ionescu@example.test', '+40722111222', 'Str. Ficusului 18, Sector 1, Bucuresti', TRUE, 3, 2),
    ('individual', 'Andrei Dumitrescu', '1790723456789', NULL, 'andrei.dumitrescu@example.test', '+40733111333', 'Str. Observatorului 42, Cluj-Napoca', TRUE, 8, 1),
    ('individual', 'Elena Stan', '2920415123456', NULL, 'elena.stan@example.test', '+40744111444', 'Str. Pacurari 91, Iasi', TRUE, 14, 1),
    ('individual', 'George Marinescu', '1741111223344', NULL, 'george.marinescu@example.test', '+40755111555', 'Bd. Take Ionescu 27, Timisoara', TRUE, 21, 3),
    ('individual', 'Ioana Radu', '2910505667788', NULL, 'ioana.radu@example.test', '+40766111666', 'Str. Republicii 15, Brasov', TRUE, 5, 2),
    ('individual', 'Vlad Georgescu', '1820922334455', NULL, 'vlad.georgescu@example.test', '+40777111777', 'Bd. Mamaia 121, Constanta', TRUE, 33, 1),
    ('individual', 'Simona Matei', '2881222445566', NULL, 'simona.matei@example.test', '+40788111888', 'Str. Mitropoliei 6, Sibiu', TRUE, 46, 2),
    ('individual', 'Radu Florescu', '1780722123456', NULL, 'radu.florescu@example.test', '+40799111999', 'Str. Democratiei 33, Ploiesti', TRUE, 61, 1),
    ('company', 'Carpatica Retail SRL', NULL, 'RO40123456', 'carpatica.retail@example.test', '+40259444111', 'Calea Aradului 54, Oradea', TRUE, 72, 1),
    ('individual', 'Alexandru Vulcu', '1900101123456', NULL, 'alexandru.vulcu@zerorisk.ro', '+40700123456', 'Str. Demo Claims 1, Bucuresti', TRUE, 1, 1)
)
INSERT INTO customer (
    type,
    full_name,
    national_id,
    company_id,
    email,
    phone,
    address_id,
    customer_profile_completed_at,
    customer_profile_updated_at,
    customer_profile_completion_source,
    profile_update_count
)
SELECT
    demo_customers.type,
    demo_customers.full_name,
    demo_customers.national_id,
    demo_customers.company_id,
    demo_customers.email,
    demo_customers.phone,
    address.id,
    CASE
        WHEN demo_customers.completed THEN NOW() - (demo_customers.updated_days_ago * INTERVAL '1 day')
        ELSE NULL
    END,
    NOW() - (demo_customers.updated_days_ago * INTERVAL '1 day'),
    CASE WHEN demo_customers.completed THEN 'seed' ELSE NULL END,
    demo_customers.profile_update_count
FROM demo_customers
JOIN address ON address.full_text = demo_customers.address_full_text
WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE customer.email = demo_customers.email
);

INSERT INTO auth_user (
    email,
    password_hash,
    role,
    full_name,
    phone,
    client_id,
    is_active
)
VALUES
(
    'ana.popescu@client.com',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Ana Popescu',
    '+40 700 111 222',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com' LIMIT 1),
    TRUE
),
(
    'ioana.polita@ultrasafe.ro',
    '$2b$12$A/5BEub2oel880f0aalg2uz.suu8tnJcvl7A4dREmlVZ0s3fV.2Pe',
    'underwriter',
    'Ioana Poliță',
    '+40 700 333 444',
    NULL,
    TRUE
),
(
    'mihai.ionescu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Mihai Ionescu',
    '+40722111222',
    (SELECT id FROM customer WHERE email = 'mihai.ionescu@example.test' LIMIT 1),
    TRUE
),
(
    'andrei.dumitrescu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Andrei Dumitrescu',
    '+40733111333',
    (SELECT id FROM customer WHERE email = 'andrei.dumitrescu@example.test' LIMIT 1),
    TRUE
),
(
    'elena.stan@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Elena Stan',
    '+40744111444',
    (SELECT id FROM customer WHERE email = 'elena.stan@example.test' LIMIT 1),
    TRUE
),
(
    'george.marinescu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'George Marinescu',
    '+40755111555',
    (SELECT id FROM customer WHERE email = 'george.marinescu@example.test' LIMIT 1),
    TRUE
),
(
    'ioana.radu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Ioana Radu',
    '+40766111666',
    (SELECT id FROM customer WHERE email = 'ioana.radu@example.test' LIMIT 1),
    TRUE
),
(
    'vlad.georgescu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Vlad Georgescu',
    '+40777111777',
    (SELECT id FROM customer WHERE email = 'vlad.georgescu@example.test' LIMIT 1),
    TRUE
),
(
    'simona.matei@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Simona Matei',
    '+40788111888',
    (SELECT id FROM customer WHERE email = 'simona.matei@example.test' LIMIT 1),
    TRUE
),
(
    'radu.florescu@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Radu Florescu',
    '+40799111999',
    (SELECT id FROM customer WHERE email = 'radu.florescu@example.test' LIMIT 1),
    TRUE
),
(
    'carpatica.retail@example.test',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Carpatica Retail SRL',
    '+40259444111',
    (SELECT id FROM customer WHERE email = 'carpatica.retail@example.test' LIMIT 1),
    TRUE
),
(
    'alexandru.vulcu@zerorisk.ro',
    '$2b$12$Qcv1M6ig/i2CIbHtgX8Uve89X/IXBX6efjKnNKtRgNWJ.r95hniIW',
    'client',
    'Alexandru Vulcu',
    '+40700123456',
    (SELECT id FROM customer WHERE email = 'alexandru.vulcu@zerorisk.ro' LIMIT 1),
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    full_name = EXCLUDED.full_name,
    phone = EXCLUDED.phone,
    client_id = EXCLUDED.client_id,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

WITH demo_assets (
    customer_email,
    asset_type,
    usage_type,
    construction_type,
    year_built,
    floor,
    area_sqm,
    declared_value,
    occupancy,
    previous_claims_count,
    address_full_text,
    created_days_ago
) AS (
    VALUES
    ('mihai.ionescu@example.test', 'apartment', 'residential', 'concrete', 2009, 3, 74.00, 420000.00, 'owner_occupied', 1, 'Str. Ficusului 18, Sector 1, Bucuresti', 18),
    ('andrei.dumitrescu@example.test', 'house', 'residential', 'brick', 1996, NULL, 136.00, 610000.00, 'owner_occupied', 0, 'Str. Observatorului 42, Cluj-Napoca', 38),
    ('elena.stan@example.test', 'apartment', 'residential', 'concrete', 2014, 2, 58.00, 330000.00, 'owner_occupied', 0, 'Str. Pacurari 91, Iasi', 28),
    ('george.marinescu@example.test', 'house', 'residential', 'brick', 2001, NULL, 118.00, 470000.00, 'owner_occupied', 1, 'Bd. Take Ionescu 27, Timisoara', 34),
    ('ioana.radu@example.test', 'apartment', 'residential', 'concrete', 2017, 5, 63.00, 360000.00, 'owner_occupied', 0, 'Str. Republicii 15, Brasov', 55),
    ('vlad.georgescu@example.test', 'apartment', 'residential', 'concrete', 2007, 4, 82.00, 410000.00, 'owner_occupied', 1, 'Bd. Mamaia 121, Constanta', 42),
    ('simona.matei@example.test', 'house', 'residential', 'brick', 1989, NULL, 96.00, 300000.00, 'owner_occupied', 0, 'Str. Mitropoliei 6, Sibiu', 51),
    ('radu.florescu@example.test', 'house', 'residential', 'brick', 1978, NULL, 104.00, 340000.00, 'owner_occupied', 1, 'Str. Democratiei 33, Ploiesti', 64),
    ('alexandru.vulcu@zerorisk.ro', 'apartment', 'residential', 'concrete', 2011, 6, 69.00, 360000.00, 'owner_occupied', 0, 'Str. Demo Claims 1, Bucuresti', 12),
    ('carpatica.retail@example.test', 'commercial', 'commercial', 'steel', 2012, NULL, 240.00, 1250000.00, 'tenant_occupied', 2, 'Calea Aradului 54, Oradea', 70)
)
INSERT INTO insured_asset (
    customer_id,
    asset_type,
    usage_type,
    construction_type,
    year_built,
    floor,
    area_sqm,
    declared_value,
    occupancy,
    previous_claims_count,
    address_id,
    created_at,
    updated_at
)
SELECT
    customer.id,
    demo_assets.asset_type,
    demo_assets.usage_type,
    demo_assets.construction_type,
    demo_assets.year_built,
    demo_assets.floor,
    demo_assets.area_sqm,
    demo_assets.declared_value,
    demo_assets.occupancy,
    demo_assets.previous_claims_count,
    address.id,
    NOW() - (demo_assets.created_days_ago * INTERVAL '1 day'),
    NOW() - (demo_assets.created_days_ago * INTERVAL '1 day')
FROM demo_assets
JOIN customer ON customer.email = demo_assets.customer_email
JOIN address ON address.full_text = demo_assets.address_full_text
WHERE NOT EXISTS (
    SELECT 1
    FROM insured_asset existing
    WHERE existing.customer_id = customer.id
      AND existing.address_id = address.id
      AND existing.asset_type = demo_assets.asset_type
);

WITH converted_demo_quotes (
    request_id,
    customer_email,
    request_status,
    asset_full_text,
    final_premium,
    coverage_amount
) AS (
    VALUES
    ('33333333-3333-4333-8333-000000000101'::uuid, 'mihai.ionescu@example.test', 'auto_accepted', 'Str. Ficusului 18, Sector 1, Bucuresti', 1160.00, 420000.00),
    ('33333333-3333-4333-8333-000000000102'::uuid, 'andrei.dumitrescu@example.test', 'auto_accepted', 'Str. Observatorului 42, Cluj-Napoca', 1710.00, 610000.00),
    ('33333333-3333-4333-8333-000000000103'::uuid, 'ioana.radu@example.test', 'auto_accepted', 'Str. Republicii 15, Brasov', 930.00, 360000.00),
    ('33333333-3333-4333-8333-000000000104'::uuid, 'carpatica.retail@example.test', 'auto_accepted', 'Calea Aradului 54, Oradea', 3890.00, 1250000.00),
    ('33333333-3333-4333-8333-000000000301'::uuid, 'elena.stan@example.test', 'auto_accepted', 'Str. Pacurari 91, Iasi', 1040.00, 330000.00),
    ('33333333-3333-4333-8333-000000000302'::uuid, 'george.marinescu@example.test', 'auto_accepted', 'Bd. Take Ionescu 27, Timisoara', 1475.00, 470000.00),
    ('33333333-3333-4333-8333-000000000303'::uuid, 'vlad.georgescu@example.test', 'auto_accepted', 'Bd. Mamaia 121, Constanta', 1340.00, 410000.00),
    ('33333333-3333-4333-8333-000000000304'::uuid, 'simona.matei@example.test', 'auto_accepted', 'Str. Mitropoliei 6, Sibiu', 980.00, 300000.00),
    ('33333333-3333-4333-8333-000000000305'::uuid, 'radu.florescu@example.test', 'auto_accepted', 'Str. Democratiei 33, Ploiesti', 1190.00, 340000.00),
    ('33333333-3333-4333-8333-000000000401'::uuid, 'alexandru.vulcu@zerorisk.ro', 'auto_accepted', 'Str. Demo Claims 1, Bucuresti', 1025.00, 360000.00)
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
    converted_demo_quotes.request_id,
    customer.id,
    converted_demo_quotes.request_status,
    jsonb_build_object(
        'type', customer.type,
        'full_name', customer.full_name,
        'national_id', customer.national_id,
        'company_id', customer.company_id,
        'email', customer.email,
        'phone', customer.phone,
        'address', customer_address.full_text
    ),
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
    ),
    '[{"step":"demo_conversion","value":"Converted demo quote source for exactly one contract."}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    jsonb_build_object(
        'pricing', jsonb_build_object(
            'base_premium', converted_demo_quotes.final_premium,
            'final_premium', converted_demo_quotes.final_premium
        ),
        'request_details', jsonb_build_object(
            'coverage_amount', converted_demo_quotes.coverage_amount,
            'security_features', jsonb_build_array()
        )
    ),
    NOW(),
    NOW()
FROM converted_demo_quotes
JOIN customer ON customer.email = converted_demo_quotes.customer_email
JOIN address customer_address ON customer_address.id = customer.address_id
JOIN insured_asset asset ON asset.customer_id = customer.id
JOIN address asset_address ON asset_address.id = asset.address_id
    AND asset_address.full_text = converted_demo_quotes.asset_full_text
ON CONFLICT (request_id) DO UPDATE SET
    client_id = EXCLUDED.client_id,
    request_status = EXCLUDED.request_status,
    client_data = EXCLUDED.client_data,
    asset_data = EXCLUDED.asset_data,
    quote_steps = EXCLUDED.quote_steps,
    mandatory_data_status = EXCLUDED.mandatory_data_status,
    pricing_preview = EXCLUDED.pricing_preview,
    updated_at = NOW();

INSERT INTO quote_document (
    id,
    quote_request_id,
    template_id,
    generation_status,
    rendered_text,
    rendered_json,
    file_url,
    created_at,
    updated_at
)
VALUES
(
    1101,
    '33333333-3333-4333-8333-000000000101',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-MIHAI-2026-000201.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-MIHAI-2026-000201-quote.pdf',
    NOW(),
    NOW()
),
(
    1102,
    '33333333-3333-4333-8333-000000000102',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-ANDREI-2026-000202.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-ANDREI-2026-000202-quote.pdf',
    NOW(),
    NOW()
),
(
    1103,
    '33333333-3333-4333-8333-000000000103',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-IOANA-2026-000203.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-IOANA-2026-000203-quote.pdf',
    NOW(),
    NOW()
),
(
    1104,
    '33333333-3333-4333-8333-000000000104',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-CARPATICA-2026-000204.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-CARPATICA-2026-000204-quote.pdf',
    NOW(),
    NOW()
),
(
    1201,
    '33333333-3333-4333-8333-000000000301',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-ELENA-2026-000301.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-ELENA-2026-000301-quote.pdf',
    NOW(),
    NOW()
),
(
    1202,
    '33333333-3333-4333-8333-000000000302',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-GEORGE-2026-000302.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-GEORGE-2026-000302-quote.pdf',
    NOW(),
    NOW()
),
(
    1203,
    '33333333-3333-4333-8333-000000000303',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-VLAD-2026-000303.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-VLAD-2026-000303-quote.pdf',
    NOW(),
    NOW()
),
(
    1204,
    '33333333-3333-4333-8333-000000000304',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-SIMONA-2026-000304.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-SIMONA-2026-000304-quote.pdf',
    NOW(),
    NOW()
),
(
    1205,
    '33333333-3333-4333-8333-000000000305',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-RADU-2026-000305.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-RADU-2026-000305-quote.pdf',
    NOW(),
    NOW()
),
(
    1206,
    '33333333-3333-4333-8333-000000000401',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-DEMO-ALEX-2026-000401.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-DEMO-ALEX-2026-000401-quote.pdf',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    quote_request_id = EXCLUDED.quote_request_id,
    template_id = EXCLUDED.template_id,
    generation_status = EXCLUDED.generation_status,
    rendered_text = EXCLUDED.rendered_text,
    rendered_json = EXCLUDED.rendered_json,
    file_url = EXCLUDED.file_url,
    updated_at = NOW();

DELETE FROM pricing
WHERE contract_id IN (
    '10000000-0000-0000-0000-000000000101',
    '10000000-0000-0000-0000-000000000102',
    '10000000-0000-0000-0000-000000000103',
    '10000000-0000-0000-0000-000000000104',
    '10000000-0000-0000-0000-000000000301',
    '10000000-0000-0000-0000-000000000302',
    '10000000-0000-0000-0000-000000000303',
    '10000000-0000-0000-0000-000000000304',
    '10000000-0000-0000-0000-000000000305',
    '10000000-0000-0000-0000-000000000401'
);

WITH demo_contracts (
    id,
    contract_number,
    customer_email,
    template_document_type,
    status,
    source_quote_request_id,
    source_quote_document_id,
    issue_days_ago,
    effective_days_ago,
    expiration_days_from_now,
    base_premium,
    final_premium,
    payment_plan_type,
    installments
) AS (
    VALUES
    ('10000000-0000-0000-0000-000000000101'::uuid, 'PAD-MIHAI-2026-000201', 'mihai.ionescu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000101'::uuid, 1101, 18, 12, 353, 980.00, 1160.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000102'::uuid, 'PAD-ANDREI-2026-000202', 'andrei.dumitrescu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000102'::uuid, 1102, 38, 30, 335, 1450.00, 1710.00, 'quarterly', 4),
    ('10000000-0000-0000-0000-000000000103'::uuid, 'PAD-IOANA-2026-000203', 'ioana.radu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000103'::uuid, 1103, 55, 45, 320, 880.00, 930.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000104'::uuid, 'PAD-CARPATICA-2026-000204', 'carpatica.retail@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000104'::uuid, 1104, 70, 62, 300, 3200.00, 3890.00, 'monthly', 12),
    ('10000000-0000-0000-0000-000000000301'::uuid, 'PAD-DEMO-ELENA-2026-000301', 'elena.stan@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000301'::uuid, 1201, 28, 24, 341, 900.00, 1040.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000302'::uuid, 'PAD-DEMO-GEORGE-2026-000302', 'george.marinescu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000302'::uuid, 1202, 34, 29, 336, 1260.00, 1475.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000303'::uuid, 'PAD-DEMO-VLAD-2026-000303', 'vlad.georgescu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000303'::uuid, 1203, 42, 35, 330, 1130.00, 1340.00, 'quarterly', 4),
    ('10000000-0000-0000-0000-000000000304'::uuid, 'PAD-DEMO-SIMONA-2026-000304', 'simona.matei@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000304'::uuid, 1204, 51, 44, 321, 820.00, 980.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000305'::uuid, 'PAD-DEMO-RADU-2026-000305', 'radu.florescu@example.test', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000305'::uuid, 1205, 64, 58, 307, 980.00, 1190.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000401'::uuid, 'PAD-DEMO-ALEX-2026-000401', 'alexandru.vulcu@zerorisk.ro', 'insurance_contract', 'issued', '33333333-3333-4333-8333-000000000401'::uuid, 1206, 12, 8, 357, 880.00, 1025.00, 'annual', 1)
)
INSERT INTO contract (
    id,
    contract_number,
    document_type,
    document_version,
    insurer_id,
    customer_id,
    insured_asset_id,
    issue_date,
    effective_date,
    expiration_date,
    jurisdiction,
    governing_law,
    currency,
    status,
    source_quote_request_id,
    source_quote_document_id,
    created_at,
    updated_at
)
SELECT
    demo_contracts.id,
    demo_contracts.contract_number,
    demo_contracts.template_document_type,
    '1.0',
    (SELECT id FROM insurer WHERE name = 'Asigurator Demo SA' LIMIT 1),
    customer.id,
    (
        SELECT insured_asset.id
        FROM insured_asset
        WHERE insured_asset.customer_id = customer.id
        ORDER BY insured_asset.id DESC
        LIMIT 1
    ),
    CURRENT_DATE - demo_contracts.issue_days_ago,
    CURRENT_DATE - demo_contracts.effective_days_ago,
    CURRENT_DATE + demo_contracts.expiration_days_from_now,
    'Romania',
    'Legea 260/2008',
    'RON',
    demo_contracts.status,
    demo_contracts.source_quote_request_id,
    demo_contracts.source_quote_document_id,
    NOW() - (demo_contracts.issue_days_ago * INTERVAL '1 day'),
    NOW() - (demo_contracts.effective_days_ago * INTERVAL '1 day')
FROM demo_contracts
JOIN customer ON customer.email = demo_contracts.customer_email
ON CONFLICT (id) DO UPDATE SET
    contract_number = EXCLUDED.contract_number,
    document_type = EXCLUDED.document_type,
    document_version = EXCLUDED.document_version,
    insurer_id = EXCLUDED.insurer_id,
    customer_id = EXCLUDED.customer_id,
    insured_asset_id = EXCLUDED.insured_asset_id,
    issue_date = EXCLUDED.issue_date,
    effective_date = EXCLUDED.effective_date,
    expiration_date = EXCLUDED.expiration_date,
    jurisdiction = EXCLUDED.jurisdiction,
    governing_law = EXCLUDED.governing_law,
    currency = EXCLUDED.currency,
    status = EXCLUDED.status,
    source_quote_request_id = EXCLUDED.source_quote_request_id,
    source_quote_document_id = EXCLUDED.source_quote_document_id,
    updated_at = EXCLUDED.updated_at;

WITH demo_pricing (
    contract_id,
    base_premium_ron,
    final_premium_ron,
    payment_plan_type,
    installments
) AS (
    VALUES
    ('10000000-0000-0000-0000-000000000101'::uuid, 980.00, 1160.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000102'::uuid, 1450.00, 1710.00, 'quarterly', 4),
    ('10000000-0000-0000-0000-000000000103'::uuid, 880.00, 930.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000104'::uuid, 3200.00, 3890.00, 'monthly', 12),
    ('10000000-0000-0000-0000-000000000301'::uuid, 900.00, 1040.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000302'::uuid, 1260.00, 1475.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000303'::uuid, 1130.00, 1340.00, 'quarterly', 4),
    ('10000000-0000-0000-0000-000000000304'::uuid, 820.00, 980.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000305'::uuid, 980.00, 1190.00, 'annual', 1),
    ('10000000-0000-0000-0000-000000000401'::uuid, 880.00, 1025.00, 'annual', 1)
)
INSERT INTO pricing (
    contract_id,
    base_premium_ron,
    adjustments_json,
    final_premium_ron,
    payment_plan_type,
    installments
)
SELECT
    contract_id,
    base_premium_ron,
    '[{"source":"DEMO_RISK_MODEL","type":"percentage","value":8.00}]'::jsonb,
    final_premium_ron,
    payment_plan_type,
    installments
FROM demo_pricing;

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
VALUES
(
    '11111111-1111-4111-8111-000000000001',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'auto_accepted',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Apartment","usage_type":"Owner occupied","construction_type":"Concrete","year_built":1986,"area_sqm":68,"declared_value":350000,"occupancy":"Owner occupied","previous_claims_count":2,"address":{"country":"Romania","county":"Bucuresti","city":"Bucuresti","street":"Str. Lalelelor","number":"12","postal_code":"031234","full_text":"Str. Lalelelor 12, Sector 3, Bucuresti"}}'::jsonb,
    '[{"step":"intake","value":"Approved PAD apartment quote"},{"step":"coverage","value":"350000 RON"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    jsonb_build_array(jsonb_build_object(
        'file_name', 'vasile-ownership-deed.pdf',
        'content_type', 'application/pdf',
        'size_bytes', 184320,
        'file_url', '/me/customer-profile/documents/' || pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:Property ownership document')::text || '/download',
        'metadata', jsonb_build_object(
            'label', 'Property ownership document',
            'profile_document_id', pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:Property ownership document')::text,
            'storage_key', md5('profile:ana.popescu@client.com:vasile-ownership-deed.pdf')
        )
    )),
    '{"pricing":{"base_premium":1200,"propertyUseMultiplier":1.05,"constructionMultiplier":1.0,"ageMultiplier":1.08,"claimsMultiplier":1.12,"securityDiscountPercent":0.04,"manualReviewSurcharge":0,"final_premium":1490,"explanation":["Medium flood exposure","Previous claims history reviewed"]},"risk_assessment":{"risk_score":72,"triggered_rules":["FLOOD_EXPOSURE","CLAIMS_HISTORY"]},"request_details":{"coverage_amount":350000,"security_features":["Alarm","Smoke detector"],"systems_updated":"Electrical system updated in 2021","location_risks":"Urban flood exposure"}}'::jsonb,
    NOW(),
    NOW()
),
(
    '11111111-1111-4111-8111-000000000002',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'underwriter_review',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"House","usage_type":"Owner occupied","construction_type":"Brick","year_built":1998,"area_sqm":124,"declared_value":620000,"occupancy":"Owner occupied","previous_claims_count":0,"address":{"country":"Romania","county":"Ilfov","city":"Otopeni","street":"Str. Aviatorilor","number":"8","postal_code":"075100","full_text":"Str. Aviatorilor 8, Otopeni"}}'::jsonb,
    '[{"step":"intake","value":"House quote under review"},{"step":"risk","value":"Manual review for high declared value"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    jsonb_build_array(jsonb_build_object(
        'file_name', 'vasile-property-photos.pdf',
        'content_type', 'application/pdf',
        'size_bytes', 734003,
        'file_url', '/me/customer-profile/documents/' || pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:Property photos')::text || '/download',
        'metadata', jsonb_build_object(
            'label', 'Property photos',
            'profile_document_id', pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:Property photos')::text,
            'storage_key', md5('profile:ana.popescu@client.com:vasile-property-photos.pdf')
        )
    )),
    '{"pricing":{"base_premium":1800,"propertyUseMultiplier":1.05,"constructionMultiplier":1.02,"ageMultiplier":1.0,"claimsMultiplier":1.0,"securityDiscountPercent":0.03,"manualReviewSurcharge":150,"final_premium":2035,"explanation":["High declared value","Manual review surcharge"]},"risk_assessment":{"risk_score":68,"triggered_rules":["HIGH_VALUE_PROPERTY"]},"request_details":{"coverage_amount":620000,"security_features":["Security cameras","Security door"],"systems_updated":"Heating system updated in 2023"}}'::jsonb,
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '2 days'
),
(
    '11111111-1111-4111-8111-000000000003',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'quote_ready',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Apartment","usage_type":"Rented","construction_type":"Concrete","year_built":2010,"area_sqm":54,"declared_value":280000,"occupancy":"Rented","previous_claims_count":0,"address":{"country":"Romania","county":"Cluj","city":"Cluj-Napoca","street":"Calea Dorobantilor","number":"44","postal_code":"400117","full_text":"Calea Dorobantilor 44, Cluj-Napoca"}}'::jsonb,
    '[{"step":"pricing","value":"Quote ready for client"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":900,"propertyUseMultiplier":1.08,"constructionMultiplier":1.0,"ageMultiplier":0.96,"claimsMultiplier":1.0,"securityDiscountPercent":0.01,"manualReviewSurcharge":0,"final_premium":925,"explanation":["Rented usage adjustment"]},"risk_assessment":{"risk_score":56,"triggered_rules":["RENTED_PROPERTY"]},"request_details":{"coverage_amount":280000,"security_features":["Smoke detector"],"systems_updated":"Unknown"}}'::jsonb,
    NOW() - INTERVAL '6 days',
    NOW() - INTERVAL '6 days'
),
(
    '11111111-1111-4111-8111-000000000004',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'pricing_in_progress',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Commercial","usage_type":"Commercial use","construction_type":"Steel","year_built":2005,"area_sqm":210,"declared_value":950000,"occupancy":"Commercial use","previous_claims_count":1,"address":{"country":"Romania","county":"Timis","city":"Timisoara","street":"Bd. Revolutiei","number":"3","postal_code":"300024","full_text":"Bd. Revolutiei 3, Timisoara"}}'::jsonb,
    '[{"step":"pricing","value":"Pricing calculation in progress"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":3200,"propertyUseMultiplier":1.25,"constructionMultiplier":0.98,"ageMultiplier":1.02,"claimsMultiplier":1.06,"securityDiscountPercent":0.02,"manualReviewSurcharge":300,"final_premium":4200,"explanation":["Commercial use","Manual pricing review"]},"risk_assessment":{"risk_score":81,"triggered_rules":["COMMERCIAL_USE","HIGH_VALUE_PROPERTY"]},"request_details":{"coverage_amount":950000,"security_features":["Security cameras","Security guard"],"high_value_items":"Office equipment and stock"}}'::jsonb,
    NOW() - INTERVAL '15 days',
    NOW() - INTERVAL '15 days'
),
(
    '11111111-1111-4111-8111-000000000005',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'approved',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Apartment","usage_type":"Owner occupied","construction_type":"Concrete","year_built":2018,"area_sqm":72,"declared_value":390000,"occupancy":"Owner occupied","previous_claims_count":0,"address":{"country":"Romania","county":"Brasov","city":"Brasov","street":"Str. Muresenilor","number":"19","postal_code":"500026","full_text":"Str. Muresenilor 19, Brasov"}}'::jsonb,
    '[{"step":"approval","value":"Quote approved and contract generated for client signature"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    jsonb_build_array(jsonb_build_object(
        'file_name', 'vasile-id-document.pdf',
        'content_type', 'application/pdf',
        'size_bytes', 98304,
        'file_url', '/me/customer-profile/documents/' || pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:ID document')::text || '/download',
        'metadata', jsonb_build_object(
            'label', 'ID document',
            'profile_document_id', pg_temp.demo_seed_uuid('profile-document:ana.popescu@client.com:ID document')::text,
            'storage_key', md5('profile:ana.popescu@client.com:vasile-id-document.pdf')
        )
    )),
    '{"pricing":{"base_premium":980,"propertyUseMultiplier":1.0,"constructionMultiplier":1.0,"ageMultiplier":0.94,"claimsMultiplier":1.0,"securityDiscountPercent":0.05,"manualReviewSurcharge":0,"final_premium":875,"explanation":["Recent construction","Security discount applied"]},"risk_assessment":{"risk_score":42,"triggered_rules":["LOW_RISK_PROPERTY"]},"request_details":{"coverage_amount":390000,"security_features":["Alarm","Smoke detector","Security door"]}}'::jsonb,
    NOW() - INTERVAL '40 days',
    NOW() - INTERVAL '39 days'
),
(
    '11111111-1111-4111-8111-000000000006',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'disapproved',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"House","usage_type":"Vacant","construction_type":"Wood","year_built":1940,"area_sqm":96,"declared_value":410000,"occupancy":"Vacant","previous_claims_count":3,"address":{"country":"Romania","county":"Prahova","city":"Sinaia","street":"Str. Furnica","number":"6","postal_code":"106100","full_text":"Str. Furnica 6, Sinaia"}}'::jsonb,
    '[{"step":"rejection_reason","rejection_reason":"Vacant wooden property with repeated claims requires specialist underwriting."}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":2100,"propertyUseMultiplier":1.2,"constructionMultiplier":1.35,"ageMultiplier":1.3,"claimsMultiplier":1.25,"securityDiscountPercent":0,"manualReviewSurcharge":500,"final_premium":5100,"explanation":["Vacancy risk","Wood construction","Claims history"]},"risk_assessment":{"risk_score":94,"triggered_rules":["VACANT_PROPERTY","WOOD_CONSTRUCTION","CLAIMS_HISTORY"]},"request_details":{"coverage_amount":410000,"security_features":[],"long_vacancy":"More than 90 days per year"}}'::jsonb,
    NOW() - INTERVAL '75 days',
    NOW() - INTERVAL '74 days'
),
(
    '11111111-1111-4111-8111-000000000007',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'field_review_required',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"House","usage_type":"Holiday home","construction_type":"Brick","year_built":1972,"area_sqm":118,"declared_value":520000,"occupancy":"Holiday home","previous_claims_count":1,"address":{"country":"Romania","county":"Constanta","city":"Eforie Nord","street":"Str. Marii","number":"22","postal_code":"905350","full_text":"Str. Marii 22, Eforie Nord"}}'::jsonb,
    '[{"step":"field_review","value":"Coastal exposure requires field review"}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":1600,"propertyUseMultiplier":1.1,"constructionMultiplier":1.0,"ageMultiplier":1.12,"claimsMultiplier":1.05,"securityDiscountPercent":0.02,"manualReviewSurcharge":250,"final_premium":2100,"explanation":["Coastal storm exposure","Holiday-home occupancy"]},"risk_assessment":{"risk_score":77,"triggered_rules":["STORM_EXPOSURE","HOLIDAY_HOME"]},"request_details":{"coverage_amount":520000,"security_features":["Security cameras"],"location_risks":"Coastal wind exposure"}}'::jsonb,
    NOW() - INTERVAL '130 days',
    NOW() - INTERVAL '129 days'
),
(
    '11111111-1111-4111-8111-000000000008',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'failed',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Apartment","usage_type":"Owner occupied","construction_type":"Concrete","year_built":1965,"area_sqm":48,"declared_value":210000,"occupancy":"Owner occupied","previous_claims_count":0,"address":{"country":"Romania","county":"Iasi","city":"Iasi","street":"Str. Pacurari","number":"77","postal_code":"700511","full_text":"Str. Pacurari 77, Iasi"}}'::jsonb,
    '[{"step":"failure","value":"Pricing failed due to missing external reference data"}]'::jsonb,
    '{"is_complete":false,"missing_fields":["risk_reference_data"]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":0,"propertyUseMultiplier":1,"constructionMultiplier":1,"ageMultiplier":1,"claimsMultiplier":1,"securityDiscountPercent":0,"manualReviewSurcharge":0,"final_premium":0,"explanation":["Pricing failed"]},"risk_assessment":{"risk_score":0,"triggered_rules":["REFERENCE_DATA_UNAVAILABLE"]},"request_details":{"coverage_amount":210000,"security_features":[]}}'::jsonb,
    NOW() - INTERVAL '220 days',
    NOW() - INTERVAL '220 days'
),
(
    '11111111-1111-4111-8111-000000000009',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'draft',
    '{"type":"individual","full_name":"Ana Popescu","national_id":"1900101123456","email":"ana.popescu@client.com","phone":"+40 700 111 222","address":"Str. Lalelelor 12, Sector 3, Bucuresti"}'::jsonb,
    '{"asset_type":"Apartment","usage_type":"Owner occupied","construction_type":"Concrete","year_built":2001,"area_sqm":60,"declared_value":300000,"occupancy":"Owner occupied","previous_claims_count":0,"address":{"country":"Romania","county":"Bucuresti","city":"Bucuresti","street":"Str. Atelierului","number":"2","postal_code":"040521","full_text":"Str. Atelierului 2, Bucuresti"}}'::jsonb,
    '[{"step":"draft","value":"Client draft quote"}]'::jsonb,
    '{"is_complete":false,"missing_fields":["coverage_amount"]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":0,"final_premium":0,"explanation":[]},"risk_assessment":{"risk_score":0,"triggered_rules":[]},"request_details":{"coverage_amount":300000,"security_features":[]}}'::jsonb,
    NOW() - INTERVAL '330 days',
    NOW() - INTERVAL '330 days'
)
ON CONFLICT (request_id) DO UPDATE SET
    client_id = EXCLUDED.client_id,
    request_status = EXCLUDED.request_status,
    client_data = EXCLUDED.client_data,
    asset_data = EXCLUDED.asset_data,
    quote_steps = EXCLUDED.quote_steps,
    mandatory_data_status = EXCLUDED.mandatory_data_status,
    attachments = EXCLUDED.attachments,
    pricing_preview = EXCLUDED.pricing_preview,
    updated_at = EXCLUDED.updated_at;

DELETE FROM quote_decision_audit
WHERE quote_request_id IN (
    '11111111-1111-4111-8111-000000000001',
    '11111111-1111-4111-8111-000000000006',
    '11111111-1111-4111-8111-000000000007',
    '33333333-3333-4333-8333-000000000101',
    '33333333-3333-4333-8333-000000000103',
    '33333333-3333-4333-8333-000000000104'
);

INSERT INTO quote_decision_audit (
    quote_request_id,
    previous_status,
    decision_status,
    reason,
    decided_by_auth_user_id,
    decided_by_name,
    decided_by_email,
    decided_at,
    metadata
)
VALUES
(
    '11111111-1111-4111-8111-000000000001',
    'underwriter_review',
    'approved',
    'Approved after reviewing prior claims history and flood mitigation details.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '1 day',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
),
(
    '11111111-1111-4111-8111-000000000006',
    'underwriter_review',
    'disapproved',
    'Vacant wooden property with repeated claims requires specialist underwriting outside the demo appetite.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '74 days',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
),
(
    '11111111-1111-4111-8111-000000000007',
    'underwriter_review',
    'field_review_required',
    'Coastal wind exposure requires local inspection before the quote can be released.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '129 days',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
),
(
    '33333333-3333-4333-8333-000000000101',
    'underwriter_review',
    'approved',
    'Converted demo quote approved for contract issuance.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '18 days',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
),
(
    '33333333-3333-4333-8333-000000000103',
    'underwriter_review',
    'approved',
    'Low-risk apartment quote approved after document review.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '55 days',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
),
(
    '33333333-3333-4333-8333-000000000104',
    'underwriter_review',
    'approved',
    'Commercial location accepted with pricing adjustment already reflected in the quote.',
    (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1),
    'Ioana Poliță',
    'ioana.polita@ultrasafe.ro',
    NOW() - INTERVAL '70 days',
    '{"generation_mode":"demo_seed","source":"sql/023_backend_demo_dataset.sql"}'::jsonb
);

INSERT INTO quote_document (
    id,
    quote_request_id,
    template_id,
    generation_status,
    rendered_text,
    rendered_json,
    file_url,
    created_at,
    updated_at
)
VALUES
(
    1001,
    '11111111-1111-4111-8111-000000000001',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-RISK-2026-000145. Premium: 1490 RON. Coverage amount: 350000 RON.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-RISK-2026-000145-quote.pdf',
    NOW(),
    NOW()
),
(
    1002,
    '11111111-1111-4111-8111-000000000005',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'success',
    'Generated quote document for PAD-PROPERTY-2026-000150. Premium: 875 RON. Coverage amount: 390000 RON.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed"}'::jsonb,
    '/demo/quotes/PAD-PROPERTY-2026-000150-quote.pdf',
    NOW() - INTERVAL '39 days',
    NOW() - INTERVAL '39 days'
),
(
    1003,
    '11111111-1111-4111-8111-000000000008',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO'),
    'failed',
    'Quote document generation failed because pricing data was incomplete.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"demo_seed","error":"pricing_failed"}'::jsonb,
    NULL,
    NOW() - INTERVAL '220 days',
    NOW() - INTERVAL '220 days'
)
ON CONFLICT (id) DO UPDATE SET
    quote_request_id = EXCLUDED.quote_request_id,
    template_id = EXCLUDED.template_id,
    generation_status = EXCLUDED.generation_status,
    rendered_text = EXCLUDED.rendered_text,
    rendered_json = EXCLUDED.rendered_json,
    file_url = EXCLUDED.file_url,
    updated_at = EXCLUDED.updated_at;

SELECT setval(
    pg_get_serial_sequence('quote_document', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM quote_document), 1)
);

WITH demo_quote_acceptances (
    id,
    quote_request_id,
    quote_document_id,
    signer_email,
    signer_name,
    accepted_days_ago
) AS (
    VALUES
    (1001, '11111111-1111-4111-8111-000000000001'::uuid, 1001, 'ana.popescu@client.com', 'Ana Popescu', 0),
    (1101, '33333333-3333-4333-8333-000000000101'::uuid, 1101, 'mihai.ionescu@example.test', 'Mihai Ionescu', 12),
    (1102, '33333333-3333-4333-8333-000000000102'::uuid, 1102, 'andrei.dumitrescu@example.test', 'Andrei Dumitrescu', 30),
    (1103, '33333333-3333-4333-8333-000000000103'::uuid, 1103, 'ioana.radu@example.test', 'Ioana Radu', 45),
    (1104, '33333333-3333-4333-8333-000000000104'::uuid, 1104, 'carpatica.retail@example.test', 'Carpatica Retail SRL', 62),
    (1201, '33333333-3333-4333-8333-000000000301'::uuid, 1201, 'elena.stan@example.test', 'Elena Stan', 24),
    (1202, '33333333-3333-4333-8333-000000000302'::uuid, 1202, 'george.marinescu@example.test', 'George Marinescu', 29),
    (1203, '33333333-3333-4333-8333-000000000303'::uuid, 1203, 'vlad.georgescu@example.test', 'Vlad Georgescu', 35),
    (1204, '33333333-3333-4333-8333-000000000304'::uuid, 1204, 'simona.matei@example.test', 'Simona Matei', 44),
    (1205, '33333333-3333-4333-8333-000000000305'::uuid, 1205, 'radu.florescu@example.test', 'Radu Florescu', 58),
    (1206, '33333333-3333-4333-8333-000000000401'::uuid, 1206, 'alexandru.vulcu@zerorisk.ro', 'Alexandru Vulcu', 8)
)
INSERT INTO quote_acceptance (
    id,
    quote_request_id,
    quote_document_id,
    accepted_by_auth_user_id,
    accepted_by_customer_id,
    signer_name,
    signer_email,
    signer_role,
    accepted_at,
    acceptance_method,
    acceptance_statement,
    quote_content_hash,
    metadata,
    created_at
)
SELECT
    demo_quote_acceptances.id,
    demo_quote_acceptances.quote_request_id,
    demo_quote_acceptances.quote_document_id,
    auth_user.id,
    auth_user.client_id,
    demo_quote_acceptances.signer_name,
    demo_quote_acceptances.signer_email,
    'policyholder',
    NOW() - (demo_quote_acceptances.accepted_days_ago * INTERVAL '1 day'),
    'seed',
    'I accept this quote and confirm that the supplied information is accurate.',
    'demo-quote-content-hash-' || demo_quote_acceptances.id::text,
    jsonb_build_object('generation_mode', 'demo_seed'),
    NOW() - (demo_quote_acceptances.accepted_days_ago * INTERVAL '1 day')
FROM demo_quote_acceptances
JOIN auth_user ON auth_user.email = demo_quote_acceptances.signer_email;

SELECT setval(
    pg_get_serial_sequence('quote_acceptance', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM quote_acceptance), 1)
);

UPDATE contract
SET status = 'issued',
    source_quote_request_id = '11111111-1111-4111-8111-000000000001',
    source_quote_document_id = 1001,
    source_quote_acceptance_id = 1001,
    updated_at = NOW()
WHERE id = '10000000-0000-0000-0000-000000000001';

UPDATE contract
SET status = 'generated',
    source_quote_request_id = '11111111-1111-4111-8111-000000000005',
    source_quote_document_id = 1002,
    source_quote_acceptance_id = NULL,
    updated_at = NOW()
WHERE id = '10000000-0000-0000-0000-000000000002';

UPDATE contract
SET status = 'issued',
    source_quote_acceptance_id = quote_acceptance.id,
    updated_at = NOW()
FROM quote_acceptance
WHERE contract.source_quote_request_id = quote_acceptance.quote_request_id
  AND contract.source_quote_document_id = quote_acceptance.quote_document_id;

-- Seed complete generated contract artifacts for every demo client contract.
-- Client contract views only read persisted documents/PDFs, so these rows must
-- be usable without asking the backend to regenerate anything.
DELETE FROM generated_document
WHERE id BETWEEN 1001 AND 1299;

WITH demo_contract_documents (
    document_id,
    contract_id,
    contract_number,
    source_quote_request_id,
    source_quote_document_id,
    template_code,
    template_version_hash,
    pdf_storage_key,
    pdf_filename,
    content_hash,
    pdf_content_hash,
    issue_date,
    effective_date,
    expiration_date,
    insured_name,
    phone,
    email,
    asset_type,
    asset_address,
    area_sqm,
    year_built,
    coverage_amount,
    premium,
    payment_plan
) AS (
    VALUES
    (1001, '10000000-0000-0000-0000-000000000001'::uuid, 'PAD-RISK-2026-000145', '11111111-1111-4111-8111-000000000001'::uuid, 1001, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-risk.pdf', 'PAD-RISK-2026-000145.pdf', '63b24d7deb7d0b4cfd3c77c1f2d2c0bfb309bc8d32d0c69db34508cca1dac238', 'cc074cf7019dac7615102e479496c35aa626a6fa6689223c79d8e727bb7cf509', '2026-04-20', '2026-05-01', '2027-04-30', 'Ana Popescu', '+40 700 111 222', 'ana.popescu@client.com', 'apartment', 'Str. Lalelelor 12, Sector 3, Bucuresti', '68.0', '1986', '350000.0', '1490.0', 'plata integrala'),
    (1002, '10000000-0000-0000-0000-000000000002'::uuid, 'PAD-PROPERTY-2026-000150', '11111111-1111-4111-8111-000000000005'::uuid, 1002, 'PAD_PROPERTY_RO', 'demo-template-hash-pad-property-ro-v1', 'demo-contract-pad-property.pdf', 'PAD-PROPERTY-2026-000150.pdf', 'dd8b200f08f568e2f620583ae37129a9d43ff17bc75792125292f1bc7e5831c6', 'd09195a92c772d137c5c0485912d2b7db5c22027a59f2a7d0f0d91b484608e53', '2026-04-25', '2026-05-10', '2027-05-09', 'Ana Popescu', '+40 700 111 222', 'ana.popescu@client.com', 'apartment', 'Str. Muresenilor 19, Brasov', '72.0', '2018', '390000.0', '875.0', 'plata integrala'),
    (1101, '10000000-0000-0000-0000-000000000101'::uuid, 'PAD-MIHAI-2026-000201', '33333333-3333-4333-8333-000000000101'::uuid, 1101, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-mihai.pdf', 'PAD-MIHAI-2026-000201.pdf', '8779958cc936c2fa419beb68645cdfd3ad6e544fecf2f77d7850bdca2593aa33', '08f2ef310b00400101ee1d073c0cd954f9e4cd69327982253b20d3c6d312850e', '2026-04-28', '2026-05-04', '2027-05-10', 'Mihai Ionescu', '+40722111222', 'mihai.ionescu@example.test', 'apartment', 'Str. Ficusului 18, Sector 1, Bucuresti', '74.0', '2009', '420000.0', '1160.0', 'plata integrala'),
    (1102, '10000000-0000-0000-0000-000000000102'::uuid, 'PAD-ANDREI-2026-000202', '33333333-3333-4333-8333-000000000102'::uuid, 1102, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-andrei.pdf', 'PAD-ANDREI-2026-000202.pdf', 'c15d46966619aafb2dcd902895124950edd56f0c8c2a8e5d4d4ee5832bcf1105', '6277ebe56b3adf7c0962f1c8b6ae16935b860521076ade3a17d41fb56af9dbb2', '2026-04-08', '2026-04-16', '2027-04-28', 'Andrei Dumitrescu', '+40733111333', 'andrei.dumitrescu@example.test', 'house', 'Str. Observatorului 42, Cluj-Napoca', '136.0', '1996', '610000.0', '1710.0', '4 rate trimestriale'),
    (1103, '10000000-0000-0000-0000-000000000103'::uuid, 'PAD-IOANA-2026-000203', '33333333-3333-4333-8333-000000000103'::uuid, 1103, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-ioana.pdf', 'PAD-IOANA-2026-000203.pdf', '00032438e68cfb0b9271b0a302c2100725661e9e4cd2f0d8b485b3320a1ebbb2', '32a45f6af65b2fbf8e1b67f3c5001ab6e1b9aa65ed89600a55505d58ab668bf2', '2026-03-22', '2026-04-01', '2027-04-13', 'Ioana Radu', '+40766111666', 'ioana.radu@example.test', 'apartment', 'Str. Republicii 15, Brasov', '63.0', '2017', '360000.0', '930.0', 'plata integrala'),
    (1104, '10000000-0000-0000-0000-000000000104'::uuid, 'PAD-CARPATICA-2026-000204', '33333333-3333-4333-8333-000000000104'::uuid, 1104, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-carpatica.pdf', 'PAD-CARPATICA-2026-000204.pdf', 'bbe6d65119d07f1805bc78b11197728efe37af9b28026f7986f9fbd800b5ec6f', 'a30273849abfba387d0bb0e5fe8a112bc8b5c48e5097b269f4de3d9ae9a85839', '2026-03-07', '2026-03-15', '2027-03-12', 'Carpatica Retail SRL', '+40259444111', 'carpatica.retail@example.test', 'commercial', 'Calea Aradului 54, Oradea', '240.0', '2012', '1250000.0', '3890.0', '12 rate lunare'),
    (1201, '10000000-0000-0000-0000-000000000301'::uuid, 'PAD-DEMO-ELENA-2026-000301', '33333333-3333-4333-8333-000000000301'::uuid, 1201, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-elena.pdf', 'PAD-DEMO-ELENA-2026-000301.pdf', '9fc479dbceeb557bfe6a68298f2d75005444421d7c4c38e733d974ff17ac3312', '65736ad331f747417d846df8371e76130a8c72ca2e939ac5bdfabd182e4d6f07', '2026-04-19', '2026-04-23', '2027-04-23', 'Elena Stan', '+40744111444', 'elena.stan@example.test', 'apartment', 'Str. Pacurari 91, Iasi', '58.0', '2014', '330000.0', '1040.0', 'plata integrala'),
    (1202, '10000000-0000-0000-0000-000000000302'::uuid, 'PAD-DEMO-GEORGE-2026-000302', '33333333-3333-4333-8333-000000000302'::uuid, 1202, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-george.pdf', 'PAD-DEMO-GEORGE-2026-000302.pdf', 'dde29ac4450e140230556381241742ab5438bfbd23eb926fae651044ceb802d7', '9587a62b94f9b560373dd491c69d9f10b2f2d7809863868931f3b75e9e11b781', '2026-04-13', '2026-04-18', '2027-04-18', 'George Marinescu', '+40755111555', 'george.marinescu@example.test', 'house', 'Bd. Take Ionescu 27, Timisoara', '118.0', '2001', '470000.0', '1475.0', 'plata integrala'),
    (1203, '10000000-0000-0000-0000-000000000303'::uuid, 'PAD-DEMO-VLAD-2026-000303', '33333333-3333-4333-8333-000000000303'::uuid, 1203, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-vlad.pdf', 'PAD-DEMO-VLAD-2026-000303.pdf', '0c3ef1649c003cf3ef73914d4ac2f84f86119e1e9b766292c9c5c0b82fef5514', 'ad200e710c784f59931eb0f049130ebb097ff594d2e0b51223c309a53b9781dd', '2026-04-05', '2026-04-12', '2027-04-12', 'Vlad Georgescu', '+40777111777', 'vlad.georgescu@example.test', 'apartment', 'Bd. Mamaia 121, Constanta', '82.0', '2007', '410000.0', '1340.0', '4 rate trimestriale'),
    (1204, '10000000-0000-0000-0000-000000000304'::uuid, 'PAD-DEMO-SIMONA-2026-000304', '33333333-3333-4333-8333-000000000304'::uuid, 1204, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-simona.pdf', 'PAD-DEMO-SIMONA-2026-000304.pdf', '510d22df9e17ce14c709d8df10824f1f181baff25c4cdd326896dcf03229cb45', 'c8acd97f6b61cec774a2e3aeacc5c3ee25f7e20bfdcd7001402d85f95c1837a1', '2026-03-27', '2026-04-03', '2027-04-03', 'Simona Matei', '+40788111888', 'simona.matei@example.test', 'house', 'Str. Mitropoliei 6, Sibiu', '96.0', '1989', '300000.0', '980.0', 'plata integrala'),
    (1205, '10000000-0000-0000-0000-000000000305'::uuid, 'PAD-DEMO-RADU-2026-000305', '33333333-3333-4333-8333-000000000305'::uuid, 1205, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-radu.pdf', 'PAD-DEMO-RADU-2026-000305.pdf', '884b2a5ffbc9ff5d8e89127f9fb81e6ca24e552d5a29011a86e905f96da61b21', 'db29d0ab6730aad2e23c9047638db75d2bd8ce1a571a83c0c66c71cd79d5e05e', '2026-03-14', '2026-03-20', '2027-03-20', 'Radu Florescu', '+40799111999', 'radu.florescu@example.test', 'house', 'Str. Democratiei 33, Ploiesti', '104.0', '1978', '340000.0', '1190.0', 'plata integrala'),
    (1206, '10000000-0000-0000-0000-000000000401'::uuid, 'PAD-DEMO-ALEX-2026-000401', '33333333-3333-4333-8333-000000000401'::uuid, 1206, 'PAD_STANDARD_RO', 'demo-template-hash-pad-standard-ro-v1', 'demo-contract-pad-alex.pdf', 'PAD-DEMO-ALEX-2026-000401.pdf', 'f989b489078ec11aaa6216f15eda503d489ebf3cdea95c06d56c6977f1e88523', 'c33786def17719e656008d912bac7e7fcc87453f2394d62859f760f71ea1e6df', '2026-05-05', '2026-05-09', '2027-05-09', 'Alexandru Vulcu', '+40700123456', 'alexandru.vulcu@zerorisk.ro', 'apartment', 'Str. Demo Claims 1, Bucuresti', '69.0', '2011', '360000.0', '1025.0', 'plata integrala')
),
rendered_demo_contract_documents AS (
    SELECT
        doc.*,
        array_to_string(ARRAY[
            'POLIȚĂ DE ASIGURARE A LOCUINȚEI ȘI BUNURILOR',
            '',
            'LOCUINȚĂ ȘI BUNURI',
            '',
            'Număr poliță: ' || doc.contract_number,
            'Data emiterii: ' || doc.issue_date,
            '',
            'Între:',
            '',
            '1. ASIGURĂTORUL',
            '',
            'Societatea de Asigurare Asigurator Demo SA, cu sediul în Bd. Exemplu 100, Bucuresti, înregistrată la RO12345678, denumită în continuare „Asigurător".',
            '',
            'și',
            '',
            '2. ASIGURATUL',
            '',
            'Nume și prenume: ' || doc.insured_name,
            'Telefon: ' || doc.phone,
            'Email: ' || doc.email,
            '',
            'denumit în continuare „Asigurat".',
            '',
            'CAPITOLUL I – OBIECTUL ASIGURĂRII',
            '',
            'Art. 1',
            '',
            'Prin prezenta poliță, Asigurătorul se obligă să despăgubească Asiguratul pentru daunele produse bunurilor asigurate, ca urmare a producerii riscurilor acoperite prevăzute în contract.',
            '',
            'Art. 2 – Bunuri asigurate',
            '',
            'Sunt asigurate următoarele:',
            '',
            'A. Clădire / Locuință',
            '',
            '• tip imobil: ' || doc.asset_type,
            '• adresă: ' || doc.asset_address,
            '• suprafață: ' || doc.area_sqm || ' mp',
            '• an construcție: ' || doc.year_built,
            '',
            'B. Bunuri mobile',
            '',
            '• mobilier',
            '• electrocasnice',
            '• echipamente electronice',
            '• obiecte personale',
            '• alte bunuri declarate',
            '',
            'CAPITOLUL II – RISCURI ACOPERITE',
            '',
            'Art. 3',
            '',
            'Asigurătorul acordă despăgubiri pentru daune produse direct de:',
            '',
            '• incendiu',
            '• explozie',
            '• trăsnet',
            '• furtună',
            '• grindină',
            '• inundație',
            '• avarii accidentale la instalații',
            '• cutremur (dacă este inclus suplimentar)',
            '• furt prin efracție',
            '• vandalism',
            '',
            'CAPITOLUL III – EXCLUDERI',
            '',
            'Art. 4',
            '',
            'Nu sunt acoperite:',
            '',
            '• daune provocate intenționat de Asigurat;',
            '• uzura normală;',
            '• defecte de construcție;',
            '• război, revoltă sau acte teroriste;',
            '• confiscări dispuse de autorități;',
            '• deteriorări produse prin neîntreținerea imobilului.',
            '',
            'CAPITOLUL IV – SUMA ASIGURATĂ',
            '',
            'Art. 5',
            '',
            'Suma asigurată totală este de ' || doc.coverage_amount || ' RON.',
            '',
            'Aceasta este compusă din:',
            '• suma asigurată pentru locuință: ' || doc.coverage_amount || ' RON;',
            '• suma asigurată pentru bunuri mobile: ' || doc.coverage_amount || ' RON.',
            '',
            'CAPITOLUL V – PRIMA DE ASIGURARE',
            '',
            'Art. 6',
            '',
            'Prima totală de asigurare este de: ' || doc.premium || ' RON.',
            '',
            'Modalitatea de plată agreată: ' || doc.payment_plan || '.',
            '',
            'Neplata primei poate conduce la suspendarea sau încetarea poliței.',
            '',
            'CAPITOLUL VI – PERIOADA DE ASIGURARE',
            '',
            'Art. 7',
            '',
            'Asigurarea este valabilă în perioada:',
            '',
            'de la ' || doc.effective_date,
            'până la ' || doc.expiration_date,
            '',
            'ora 00:00 – ora 24:00.',
            '',
            'CAPITOLUL VII – OBLIGAȚIILE ASIGURATULUI',
            '',
            'Art. 8',
            '',
            'Asiguratul are obligația:',
            '',
            '• să întrețină bunurile în stare bună;',
            '• să ia măsuri pentru limitarea pagubelor;',
            '• să anunțe producerea evenimentului în maximum 48 ore;',
            '• să permită constatarea daunelor.',
            '',
            'CAPITOLUL VIII – CONSTATAREA ȘI DESPĂGUBIREA',
            '',
            'Art. 9',
            '',
            'În caz de daună, Asiguratul va transmite:',
            '',
            '• notificarea evenimentului;',
            '• fotografii;',
            '• documente justificative;',
            '• acte de proprietate;',
            '• proces verbal de la Poliție (în caz de furt).',
            '',
            'Art. 10',
            '',
            'Despăgubirea se acordă în limita sumei asigurate și după evaluarea efectuată de Asigurător.',
            '',
            'Termenul de plată al despăgubirii este de maximum 15 zile de la aprobarea dosarului de daună.',
            '',
            'CAPITOLUL IX – ÎNCETAREA CONTRACTULUI',
            '',
            'Art. 11',
            '',
            'Contractul încetează:',
            '',
            '• la expirarea perioadei asigurate;',
            '• prin reziliere;',
            '• prin neplata primei;',
            '• prin distrugerea totală a bunului asigurat.',
            '',
            'CAPITOLUL X – DISPOZIȚII FINALE',
            '',
            'Art. 12',
            '',
            'Prezentul contract este guvernat de legislația română în vigoare.',
            '',
            'Orice litigiu va fi soluționat pe cale amiabilă, iar în caz contrar de instanțele competente.',
            '',
            'SEMNĂTURI',
            '',
            'ASIGURĂTOR                                                                      ASIGURAT',
            '',
            'Nume reprezentant: Mihai Ionescu                              Nume: ' || doc.insured_name,
            'Semnătură: Mihai Ionescu                                      Semnătură: ' || doc.insured_name
        ], chr(10)) AS rendered_text
    FROM demo_contract_documents doc
)
INSERT INTO generated_document (
    id,
    contract_id,
    template_id,
    generation_status,
    rendered_text,
    rendered_json,
    file_url,
    template_code,
    template_version,
    template_version_hash,
    payload_snapshot,
    generation_metadata,
    content_hash,
    pdf_storage_key,
    pdf_filename,
    pdf_content_hash,
    pdf_source_content_hash,
    pdf_generated_at,
    pdf_generation_metadata,
    created_at,
    updated_at
)
SELECT
    doc.document_id,
    doc.contract_id,
    (SELECT id FROM template WHERE template_code = doc.template_code),
    'success',
    doc.rendered_text,
    jsonb_build_object(
        'template_used', jsonb_build_object(
            'template_code', doc.template_code,
            'template_version', '1.0'
        ),
        'contract_generation_payload', jsonb_build_object(
            'document_type', 'insurance_contract',
            'contract_number', doc.contract_number,
            'source_quote_request_id', doc.source_quote_request_id,
            'source_quote_document_id', doc.source_quote_document_id
        ),
        'generation_metadata', jsonb_build_object('generation_mode', 'demo_seed')
    ),
    NULL,
    doc.template_code,
    '1.0',
    doc.template_version_hash,
    jsonb_build_object(
        'document_type', 'insurance_contract',
        'contract_number', doc.contract_number,
        'source_quote_request_id', doc.source_quote_request_id,
        'source_quote_document_id', doc.source_quote_document_id
    ),
    jsonb_build_object(
        'generation_mode', 'demo_seed',
        'source', 'sql/023_backend_demo_dataset.sql'
    ),
    doc.content_hash,
    doc.pdf_storage_key,
    doc.pdf_filename,
    doc.pdf_content_hash,
    doc.content_hash,
    doc.issue_date::date::timestamp,
    jsonb_build_object(
        'renderer', 'SimpleTextPdfRenderer',
        'renderer_version', 'contract-document-v4-unicode',
        'source', 'generated_document.rendered_text',
        'seed_source', 'sql/023_backend_demo_dataset.sql'
    ),
    doc.issue_date::date::timestamp,
    doc.issue_date::date::timestamp
FROM rendered_demo_contract_documents doc;

SELECT setval(
    pg_get_serial_sequence('generated_document', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM generated_document), 1)
);

DELETE FROM customer_profile_document
WHERE metadata ->> 'generation_mode' = 'demo_seed';

WITH demo_profile_documents (
    customer_email,
    label,
    document_type,
    file_name,
    size_bytes
) AS (
    VALUES
    ('ana.popescu@client.com', 'ID document', 'identity_document', 'vasile-id-document.pdf', 98304),
    ('ana.popescu@client.com', 'Property ownership document', 'land_registry', 'vasile-ownership-deed.pdf', 184320),
    ('ana.popescu@client.com', 'Property photos', 'property_photo_before', 'vasile-property-photos.pdf', 734003),
    ('mihai.ionescu@example.test', 'ID document', 'identity_document', 'maria-id-document.pdf', 98304),
    ('mihai.ionescu@example.test', 'Property ownership document', 'land_registry', 'maria-ownership-deed.pdf', 184320),
    ('andrei.dumitrescu@example.test', 'ID document', 'identity_document', 'andrei-id-document.pdf', 98304),
    ('andrei.dumitrescu@example.test', 'Property ownership document', 'land_registry', 'andrei-ownership-deed.pdf', 184320),
    ('elena.stan@example.test', 'ID document', 'identity_document', 'elena-id-document.pdf', 98304),
    ('elena.stan@example.test', 'Property ownership document', 'land_registry', 'elena-ownership-deed.pdf', 184320),
    ('george.marinescu@example.test', 'ID document', 'identity_document', 'george-id-document.pdf', 98304),
    ('george.marinescu@example.test', 'Property ownership document', 'land_registry', 'george-ownership-deed.pdf', 184320),
    ('ioana.radu@example.test', 'ID document', 'identity_document', 'ioana-id-document.pdf', 98304),
    ('ioana.radu@example.test', 'Property ownership document', 'land_registry', 'ioana-ownership-deed.pdf', 184320),
    ('vlad.georgescu@example.test', 'ID document', 'identity_document', 'vlad-id-document.pdf', 98304),
    ('vlad.georgescu@example.test', 'Property ownership document', 'land_registry', 'vlad-ownership-deed.pdf', 184320),
    ('simona.matei@example.test', 'ID document', 'identity_document', 'simona-id-document.pdf', 98304),
    ('simona.matei@example.test', 'Property ownership document', 'land_registry', 'simona-ownership-deed.pdf', 184320),
    ('radu.florescu@example.test', 'ID document', 'identity_document', 'radu-id-document.pdf', 98304),
    ('radu.florescu@example.test', 'Property ownership document', 'land_registry', 'radu-ownership-deed.pdf', 184320),
    ('carpatica.retail@example.test', 'Existing policy document', 'existing_policy', 'carpatica-existing-policy.pdf', 184320),
    ('carpatica.retail@example.test', 'Bank document', 'bank_document', 'carpatica-bank-document.pdf', 98304),
    ('alexandru.vulcu@zerorisk.ro', 'ID document', 'identity_document', 'alex-id-document.pdf', 98304),
    ('alexandru.vulcu@zerorisk.ro', 'Property ownership document', 'land_registry', 'alex-ownership-deed.pdf', 184320)
),
profile_document_rows AS (
    SELECT
        pg_temp.demo_seed_uuid('profile-document:' || demo_profile_documents.customer_email || ':' || demo_profile_documents.label) AS document_id,
        customer.id AS customer_id,
        demo_profile_documents.*
    FROM demo_profile_documents
    JOIN customer ON customer.email = demo_profile_documents.customer_email
)
INSERT INTO customer_profile_document (
    id,
    customer_id,
    label,
    document_type,
    file_name,
    content_type,
    size_bytes,
    storage_key,
    file_url,
    metadata,
    created_at,
    updated_at
)
SELECT
    profile_document_rows.document_id,
    profile_document_rows.customer_id,
    profile_document_rows.label,
    profile_document_rows.document_type,
    profile_document_rows.file_name,
    'application/pdf',
    profile_document_rows.size_bytes,
    md5('profile:' || profile_document_rows.customer_email || ':' || profile_document_rows.file_name),
    '/me/customer-profile/documents/' || profile_document_rows.document_id::text || '/download',
    jsonb_build_object(
        'generation_mode', 'demo_seed',
        'source', 'sql/023_backend_demo_dataset.sql',
        'document_role', profile_document_rows.document_type,
        'storage_key', md5('profile:' || profile_document_rows.customer_email || ':' || profile_document_rows.file_name)
    ),
    NOW(),
    NOW()
FROM profile_document_rows;

INSERT INTO claim_request (
    request_id,
    client_id,
    request_status,
    client_data,
    claim_data,
    attachments,
    created_at,
    updated_at
)
VALUES
(
    '22222222-2222-4222-8222-000000000001',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'submitted',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Fire',
        'incident_date', to_char(CURRENT_DATE, 'YYYY-MM-DD'),
        'incident_time', '08:35',
        'estimated_damage', 18500,
        'description', 'Kitchen fire caused smoke damage to cabinets and walls.',
        'emergency_services', true,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000001'::uuid, 'fire-department-report.pdf', 'Fire department report', 'incident_report', 'application/pdf', 245760, 'PAD-RISK-2026-000145', 'Fire', 18500, 'Kitchen fire caused smoke damage to cabinets and walls.'),
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000001'::uuid, 'kitchen-damage-photo.pdf', 'Photos from incident', 'property_photo_after', 'application/pdf', 524288, 'PAD-RISK-2026-000145', 'Fire', 18500, 'Kitchen fire caused smoke damage to cabinets and walls.')
    ),
    NOW(),
    NOW()
),
(
    '22222222-2222-4222-8222-000000000002',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'screening',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Water damage',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '1 day', 'YYYY-MM-DD'),
        'incident_time', '22:15',
        'estimated_damage', 9200,
        'description', 'Bathroom pipe leak affected flooring and lower wall area.',
        'emergency_services', false,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000002'::uuid, 'plumber-report.pdf', 'Repair report', 'repair_invoice', 'application/pdf', 198144, 'PAD-RISK-2026-000145', 'Water damage', 9200, 'Bathroom pipe leak affected flooring and lower wall area.'),
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000002'::uuid, 'water-damage-photo.pdf', 'Photos from incident', 'property_photo_after', 'application/pdf', 350000, 'PAD-RISK-2026-000145', 'Water damage', 9200, 'Bathroom pipe leak affected flooring and lower wall area.')
    ),
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day'
),
(
    '22222222-2222-4222-8222-000000000003',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'needs_underwriter_review',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Storm',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '5 days', 'YYYY-MM-DD'),
        'incident_time', '19:40',
        'estimated_damage', 12400,
        'description', 'Storm damaged balcony windows and exterior shutters.',
        'emergency_services', false,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000003'::uuid, 'storm-damage-estimate.pdf', 'Damage estimate', 'repair_estimate', 'application/pdf', 221184, 'PAD-RISK-2026-000145', 'Storm', 12400, 'Storm damaged balcony windows and exterior shutters.')
    ),
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '4 days'
),
(
    '22222222-2222-4222-8222-000000000004',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'coverage_review_required',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Theft',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '10 days', 'YYYY-MM-DD'),
        'incident_time', '03:10',
        'estimated_damage', 15800,
        'description', 'Break-in with stolen electronics and damaged entry door.',
        'emergency_services', true,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000004'::uuid, 'police-report.pdf', 'Police report', 'police_report', 'application/pdf', 264000, 'PAD-RISK-2026-000145', 'Theft', 15800, 'Break-in with stolen electronics and damaged entry door.'),
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000004'::uuid, 'entry-door-photo.pdf', 'Photos from incident', 'property_photo_after', 'application/pdf', 410000, 'PAD-RISK-2026-000145', 'Theft', 15800, 'Break-in with stolen electronics and damaged entry door.')
    ),
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '9 days'
),
(
    '22222222-2222-4222-8222-000000000005',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'in_review',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Other',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '35 days', 'YYYY-MM-DD'),
        'incident_time', '14:05',
        'estimated_damage', 6400,
        'description', 'Accidental glass breakage and interior finish damage.',
        'emergency_services', false,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000005'::uuid, 'repair-invoice.pdf', 'Repair invoice', 'repair_invoice', 'application/pdf', 146000, 'PAD-RISK-2026-000145', 'Other', 6400, 'Accidental glass breakage and interior finish damage.')
    ),
    NOW() - INTERVAL '35 days',
    NOW() - INTERVAL '33 days'
),
(
    '22222222-2222-4222-8222-000000000006',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'completed',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Water damage',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '70 days', 'YYYY-MM-DD'),
        'incident_time', '06:20',
        'estimated_damage', 4800,
        'description', 'Minor roof infiltration repaired after heavy rain.',
        'emergency_services', false,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000006'::uuid, 'roof-repair-receipt.pdf', 'Repair receipt', 'repair_invoice', 'application/pdf', 99000, 'PAD-RISK-2026-000145', 'Water damage', 4800, 'Minor roof infiltration repaired after heavy rain.')
    ),
    NOW() - INTERVAL '70 days',
    NOW() - INTERVAL '65 days'
),
(
    '22222222-2222-4222-8222-000000000007',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'failed',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Storm',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '150 days', 'YYYY-MM-DD'),
        'incident_time', '17:00',
        'estimated_damage', 0,
        'description', 'Incomplete storm claim used for failure-state demo.',
        'emergency_services', false,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    '[]'::jsonb,
    NOW() - INTERVAL '150 days',
    NOW() - INTERVAL '149 days'
),
(
    '22222222-2222-4222-8222-000000000008',
    (SELECT id FROM customer WHERE email = 'ana.popescu@client.com'),
    'submitted',
    '{"full_name":"Ana Popescu","email":"ana.popescu@client.com","phone":"+40 700 111 222"}'::jsonb,
    jsonb_build_object(
        'contract_id', '10000000-0000-0000-0000-000000000001',
        'policy_number', 'PAD-RISK-2026-000145',
        'property_address', 'Str. Lalelelor 12, Sector 3, Bucuresti',
        'claim_type', 'Fire',
        'incident_date', to_char(CURRENT_DATE - INTERVAL '300 days', 'YYYY-MM-DD'),
        'incident_time', '12:25',
        'estimated_damage', 7200,
        'description', 'Small appliance fire with smoke residue in kitchen.',
        'emergency_services', true,
        'contact_phone', '+40 700 111 222',
        'contact_email', 'ana.popescu@client.com'
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment('22222222-2222-4222-8222-000000000008'::uuid, 'smoke-cleanup-invoice.pdf', 'Cleanup invoice', 'repair_invoice', 'application/pdf', 132000, 'PAD-RISK-2026-000145', 'Fire', 7200, 'Small appliance fire with smoke residue in kitchen.')
    ),
    NOW() - INTERVAL '300 days',
    NOW() - INTERVAL '299 days'
);

WITH demo_claims (
    request_id,
    customer_email,
    request_status,
    claim_type,
    incident_days_ago,
    created_days_ago,
    incident_time,
    estimated_damage,
    description,
    contract_id,
    policy_number,
    attachment_file,
    attachment_content_type,
    attachment_size_bytes
) AS (
    VALUES
    ('22222222-2222-4222-8222-000000000009'::uuid, 'mihai.ionescu@example.test', 'submitted', 'Water damage', 0, 0, '07:45', 6800, 'Kitchen supply line leak affected flooring and lower cabinetry.', '10000000-0000-0000-0000-000000000101', 'PAD-MIHAI-2026-000201', 'mihai-water-damage-photo.pdf', 'application/pdf', 342144),
    ('22222222-2222-4222-8222-000000000010'::uuid, 'andrei.dumitrescu@example.test', 'screening', 'Storm', 0, 0, '18:10', 14300, 'High winds damaged roof tiles and attic insulation.', '10000000-0000-0000-0000-000000000102', 'PAD-ANDREI-2026-000202', 'andrei-roof-estimate.pdf', 'application/pdf', 204800),
    ('22222222-2222-4222-8222-000000000011'::uuid, 'elena.stan@example.test', 'needs_underwriter_review', 'Theft', 1, 1, '02:35', 9800, 'Break-in through balcony door with stolen electronics.', '10000000-0000-0000-0000-000000000301', 'PAD-DEMO-ELENA-2026-000301', 'elena-police-report.pdf', 'application/pdf', 251904),
    ('22222222-2222-4222-8222-000000000012'::uuid, 'george.marinescu@example.test', 'coverage_review_required', 'Fire', 2, 2, '11:20', 27600, 'Electrical panel fire caused smoke damage in hallway and living room.', '10000000-0000-0000-0000-000000000302', 'PAD-DEMO-GEORGE-2026-000302', 'george-fire-report.pdf', 'application/pdf', 300032),
    ('22222222-2222-4222-8222-000000000013'::uuid, 'ioana.radu@example.test', 'in_review', 'Other', 3, 3, '14:05', 4200, 'Accidental glass breakage in balcony door.', '10000000-0000-0000-0000-000000000103', 'PAD-IOANA-2026-000203', 'ioana-repair-invoice.pdf', 'application/pdf', 118784),
    ('22222222-2222-4222-8222-000000000014'::uuid, 'vlad.georgescu@example.test', 'submitted', 'Storm', 4, 4, '19:55', 11100, 'Coastal storm damaged exterior shutters.', '10000000-0000-0000-0000-000000000303', 'PAD-DEMO-VLAD-2026-000303', 'vlad-storm-photo.pdf', 'application/pdf', 417792),
    ('22222222-2222-4222-8222-000000000015'::uuid, 'simona.matei@example.test', 'completed', 'Water damage', 7, 7, '06:25', 5200, 'Roof infiltration after heavy rain affected one bedroom wall.', '10000000-0000-0000-0000-000000000304', 'PAD-DEMO-SIMONA-2026-000304', 'simona-roof-repair.pdf', 'application/pdf', 134144),
    ('22222222-2222-4222-8222-000000000016'::uuid, 'radu.florescu@example.test', 'failed', 'Other', 9, 9, '10:10', 0, 'Incomplete claim submitted without supporting documentation.', '10000000-0000-0000-0000-000000000305', 'PAD-DEMO-RADU-2026-000305', 'radu-incomplete-note.pdf', 'application/pdf', 45056),
    ('22222222-2222-4222-8222-000000000017'::uuid, 'carpatica.retail@example.test', 'screening', 'Theft', 12, 12, '03:40', 34500, 'Retail storage area break-in with stock and door damage.', '10000000-0000-0000-0000-000000000104', 'PAD-CARPATICA-2026-000204', 'carpatica-police-report.pdf', 'application/pdf', 278528),
    ('22222222-2222-4222-8222-000000000018'::uuid, 'mihai.ionescu@example.test', 'in_review', 'Fire', 16, 16, '16:15', 8900, 'Small appliance fire caused smoke residue and cabinet damage.', '10000000-0000-0000-0000-000000000101', 'PAD-MIHAI-2026-000201', 'mihai-smoke-cleanup-invoice.pdf', 'application/pdf', 161792),
    ('22222222-2222-4222-8222-000000000019'::uuid, 'andrei.dumitrescu@example.test', 'submitted', 'Other', 20, 20, '12:30', 3600, 'Garage door impact damage during parking incident.', '10000000-0000-0000-0000-000000000102', 'PAD-ANDREI-2026-000202', 'andrei-garage-photo.pdf', 'application/pdf', 301056),
    ('22222222-2222-4222-8222-000000000020'::uuid, 'elena.stan@example.test', 'completed', 'Water damage', 25, 25, '21:10', 7400, 'Bathroom pipe leak affected laminate flooring.', '10000000-0000-0000-0000-000000000301', 'PAD-DEMO-ELENA-2026-000301', 'elena-plumber-report.pdf', 'application/pdf', 186368),
    ('22222222-2222-4222-8222-000000000021'::uuid, 'george.marinescu@example.test', 'submitted', 'Storm', 32, 32, '17:45', 12800, 'Hailstorm damaged skylight and exterior blinds.', '10000000-0000-0000-0000-000000000302', 'PAD-DEMO-GEORGE-2026-000302', 'george-hail-photo.pdf', 'application/pdf', 512000),
    ('22222222-2222-4222-8222-000000000022'::uuid, 'ioana.radu@example.test', 'needs_underwriter_review', 'Theft', 45, 45, '04:20', 15200, 'Forced entry with jewelry and laptop theft.', '10000000-0000-0000-0000-000000000103', 'PAD-IOANA-2026-000203', 'ioana-police-report.pdf', 'application/pdf', 241664),
    ('22222222-2222-4222-8222-000000000023'::uuid, 'vlad.georgescu@example.test', 'coverage_review_required', 'Water damage', 58, 58, '08:00', 9700, 'Air conditioner condensate leak damaged ceiling and wall.', '10000000-0000-0000-0000-000000000303', 'PAD-DEMO-VLAD-2026-000303', 'vlad-contractor-estimate.pdf', 'application/pdf', 199680),
    ('22222222-2222-4222-8222-000000000024'::uuid, 'simona.matei@example.test', 'screening', 'Fire', 73, 73, '13:15', 11600, 'Chimney smoke event damaged living room textiles.', '10000000-0000-0000-0000-000000000304', 'PAD-DEMO-SIMONA-2026-000304', 'simona-fire-brigade-note.pdf', 'application/pdf', 225280),
    ('22222222-2222-4222-8222-000000000025'::uuid, 'radu.florescu@example.test', 'in_review', 'Storm', 91, 91, '20:35', 8300, 'Storm debris broke exterior window and damaged frame.', '10000000-0000-0000-0000-000000000305', 'PAD-DEMO-RADU-2026-000305', 'radu-window-estimate.pdf', 'application/pdf', 122880),
    ('22222222-2222-4222-8222-000000000026'::uuid, 'carpatica.retail@example.test', 'completed', 'Water damage', 118, 118, '05:50', 22600, 'Sprinkler malfunction damaged display inventory.', '10000000-0000-0000-0000-000000000104', 'PAD-CARPATICA-2026-000204', 'carpatica-inventory-loss.pdf', 'application/pdf', 389120),
    ('22222222-2222-4222-8222-000000000027'::uuid, 'mihai.ionescu@example.test', 'failed', 'Theft', 145, 145, '01:05', 0, 'Duplicate theft report rejected during intake reconciliation.', '10000000-0000-0000-0000-000000000101', 'PAD-MIHAI-2026-000201', 'mihai-duplicate-report.pdf', 'application/pdf', 73728),
    ('22222222-2222-4222-8222-000000000028'::uuid, 'andrei.dumitrescu@example.test', 'coverage_review_required', 'Fire', 180, 180, '15:45', 19300, 'Outdoor grill fire affected terrace facade.', '10000000-0000-0000-0000-000000000102', 'PAD-ANDREI-2026-000202', 'andrei-terrace-damage.pdf', 'application/pdf', 267264),
    ('22222222-2222-4222-8222-000000000029'::uuid, 'george.marinescu@example.test', 'completed', 'Other', 210, 210, '09:30', 3100, 'Minor vandalism damaged mailbox and entry intercom.', '10000000-0000-0000-0000-000000000302', 'PAD-DEMO-GEORGE-2026-000302', 'george-vandalism-invoice.pdf', 'application/pdf', 104448),
    ('22222222-2222-4222-8222-000000000030'::uuid, 'ioana.radu@example.test', 'in_review', 'Water damage', 240, 240, '23:10', 6700, 'Washing machine hose failure affected hallway flooring.', '10000000-0000-0000-0000-000000000103', 'PAD-IOANA-2026-000203', 'ioana-water-damage-photo.pdf', 'application/pdf', 355328),
    ('22222222-2222-4222-8222-000000000031'::uuid, 'simona.matei@example.test', 'needs_underwriter_review', 'Theft', 270, 270, '02:20', 13800, 'Storage unit theft with incomplete inventory evidence.', '10000000-0000-0000-0000-000000000304', 'PAD-DEMO-SIMONA-2026-000304', 'simona-storage-report.pdf', 'application/pdf', 172032),
    ('22222222-2222-4222-8222-000000000032'::uuid, 'carpatica.retail@example.test', 'in_review', 'Storm', 340, 340, '18:25', 41700, 'Windstorm damaged storefront signage and entry glazing.', '10000000-0000-0000-0000-000000000104', 'PAD-CARPATICA-2026-000204', 'carpatica-storefront-photo.pdf', 'application/pdf', 614400),
    ('22222222-2222-4222-8222-000000000101'::uuid, 'alexandru.vulcu@zerorisk.ro', 'completed', 'Water damage', 1, 1, '09:15', 7600, 'Demo claim for approved decision email delivery.', '10000000-0000-0000-0000-000000000401', 'PAD-DEMO-ALEX-2026-000401', 'alex-demo-claim-report.pdf', 'application/pdf', 196608)
)
INSERT INTO claim_request (
    request_id,
    client_id,
    request_status,
    client_data,
    claim_data,
    attachments,
    created_at,
    updated_at
)
SELECT
    demo_claims.request_id,
    customer.id,
    demo_claims.request_status,
    jsonb_build_object(
        'full_name', customer.full_name,
        'email', customer.email,
        'phone', customer.phone
    ),
    jsonb_build_object(
        'contract_id', demo_claims.contract_id,
        'claim_id', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'CLM-DEMO-ALEX-001'
            ELSE demo_claims.request_id::text
        END,
        'display_claim_id', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'CLM-DEMO-ALEX-001'
            ELSE NULL
        END,
        'decision', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'approved'
            ELSE NULL
        END,
        'decision_status', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'submitted'
            ELSE NULL
        END,
        'decision_justification', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'The submitted evidence supports the covered water damage loss.'
            ELSE NULL
        END,
        'decided_by', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN (SELECT id FROM auth_user WHERE email = 'ioana.polita@ultrasafe.ro' LIMIT 1)
            ELSE NULL
        END,
        'decided_by_email', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN 'ioana.polita@ultrasafe.ro'
            ELSE NULL
        END,
        'decided_at', CASE
            WHEN demo_claims.customer_email = 'alexandru.vulcu@zerorisk.ro'
                THEN to_jsonb(NOW() - INTERVAL '2 hours') #>> '{}'
            ELSE NULL
        END,
        'policy_number', demo_claims.policy_number,
        'property_address', address.full_text,
        'claim_type', demo_claims.claim_type,
        'incident_date', to_char(CURRENT_DATE - demo_claims.incident_days_ago, 'YYYY-MM-DD'),
        'incident_time', demo_claims.incident_time,
        'estimated_damage', demo_claims.estimated_damage,
        'description', demo_claims.description,
        'emergency_services', demo_claims.claim_type IN ('Fire', 'Theft'),
        'contact_phone', customer.phone,
        'contact_email', customer.email
    ),
    jsonb_build_array(
        pg_temp.demo_claim_attachment(
            demo_claims.request_id,
            demo_claims.attachment_file,
            CASE
                WHEN demo_claims.attachment_file ILIKE '%photo%' THEN 'Photos from incident'
                WHEN demo_claims.attachment_file ILIKE '%police%' THEN 'Police report'
                WHEN demo_claims.attachment_file ILIKE '%invoice%' THEN 'Repair invoice'
                WHEN demo_claims.attachment_file ILIKE '%estimate%' THEN 'Damage estimate'
                ELSE 'Demo supporting evidence'
            END,
            CASE
                WHEN demo_claims.attachment_file ILIKE '%photo%' THEN 'property_photo_after'
                WHEN demo_claims.attachment_file ILIKE '%police%' THEN 'police_report'
                WHEN demo_claims.attachment_file ILIKE '%invoice%' THEN 'repair_invoice'
                WHEN demo_claims.attachment_file ILIKE '%estimate%' THEN 'repair_estimate'
                ELSE 'supporting_document'
            END,
            demo_claims.attachment_content_type,
            demo_claims.attachment_size_bytes,
            demo_claims.policy_number,
            demo_claims.claim_type,
            demo_claims.estimated_damage,
            demo_claims.description
        )
    ),
    NOW() - (demo_claims.created_days_ago * INTERVAL '1 day'),
    NOW() - (demo_claims.created_days_ago * INTERVAL '1 day')
FROM demo_claims
JOIN customer ON customer.email = demo_claims.customer_email
JOIN address ON address.id = customer.address_id;

INSERT INTO email_messages (
    id,
    case_id,
    request_id,
    direction,
    from_email,
    to_email,
    subject,
    body,
    status,
    provider_message_id,
    error_message,
    created_at,
    sent_at
)
VALUES
(
    '44444444-4444-4444-8444-000000000101'::uuid,
    '22222222-2222-4222-8222-000000000101'::uuid,
    '22222222-2222-4222-8222-000000000101'::uuid,
    'OUTBOUND',
    'maria.tiuca@ultrasafe.ro',
    'alexandru.vulcu@zerorisk.ro',
    'Claim decision review started',
    'Hello Alex, your demo claim CLM-DEMO-ALEX-001 is under final review.',
    'SENT',
    'demo-seeded-outbound-alex-001',
    NULL,
    NOW() - INTERVAL '12 hours',
    NOW() - INTERVAL '12 hours'
),
(
    '44444444-4444-4444-8444-000000000102'::uuid,
    '22222222-2222-4222-8222-000000000101'::uuid,
    '22222222-2222-4222-8222-000000000101'::uuid,
    'INBOUND',
    'alexandru.vulcu@zerorisk.ro',
    'maria.tiuca@ultrasafe.ro',
    'Re: Claim decision review started',
    'Hello, thanks for the update. I am available for any follow-up questions.',
    'RECEIVED',
    'demo-seeded-inbound-alex-001',
    NULL,
    NOW() - INTERVAL '10 hours',
    NULL
)
ON CONFLICT (id) DO UPDATE SET
    case_id = EXCLUDED.case_id,
    request_id = EXCLUDED.request_id,
    direction = EXCLUDED.direction,
    from_email = EXCLUDED.from_email,
    to_email = EXCLUDED.to_email,
    subject = EXCLUDED.subject,
    body = EXCLUDED.body,
    status = EXCLUDED.status,
    provider_message_id = EXCLUDED.provider_message_id,
    error_message = EXCLUDED.error_message,
    created_at = EXCLUDED.created_at,
    sent_at = EXCLUDED.sent_at;

COMMIT;


