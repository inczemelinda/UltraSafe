INSERT INTO intelligence_source (
    source_id,
    name,
    country,
    source_type,
    trust_tier,
    connector_type,
    language,
    enabled,
    config_json,
    created_at,
    updated_at
)
VALUES (
    'demo_intel',
    'UltraSafe Demo Intelligence',
    'RO',
    'news',
    'trusted',
    'web_scrape',
    'ro',
    TRUE,
    '{"allowed_detail_hosts":["demo.ultrasafe.local"],"allow_external_detail_urls":false}'::jsonb,
    '2026-05-09T10:00:00+03:00',
    '2026-05-09T10:00:00+03:00'
)
ON CONFLICT (source_id) DO UPDATE SET
    name = EXCLUDED.name,
    source_type = EXCLUDED.source_type,
    trust_tier = EXCLUDED.trust_tier,
    connector_type = EXCLUDED.connector_type,
    language = EXCLUDED.language,
    enabled = EXCLUDED.enabled,
    config_json = EXCLUDED.config_json,
    updated_at = EXCLUDED.updated_at;

INSERT INTO raw_source_item (
    raw_item_id,
    source_id,
    original_url,
    canonical_url,
    published_at,
    fetched_at,
    title,
    raw_html,
    extracted_text,
    attachments_json,
    content_hash,
    fetch_status,
    parse_status,
    error_message,
    created_at
)
VALUES
    (
        '90000000-0000-0000-0000-000000000001',
        'demo_intel',
        'https://demo.ultrasafe.local/intelligence/asf-pad-earthquake-wording',
        'https://demo.ultrasafe.local/intelligence/asf-pad-earthquake-wording',
        '2026-05-09T09:00:00+03:00',
        '2026-05-09T10:00:00+03:00',
        'ASF draft PAD wording update after earthquake exposure review',
        NULL,
        'ASF published a draft proiect for consultation on PAD compulsory home insurance wording. The item discusses locuinte coverage, clauze for earthquake cutremur exposure, and how insurers should explain deductible and coverage limits to homeowners. Underwriters should treat this as Romanian property insurance context for policy wording review.',
        '[]'::jsonb,
        'demo-intel-pad-earthquake-wording-v1',
        'success',
        'success',
        NULL,
        '2026-05-09T10:00:00+03:00'
    ),
    (
        '90000000-0000-0000-0000-000000000002',
        'demo_intel',
        'https://demo.ultrasafe.local/intelligence/anm-storm-hail-warning',
        'https://demo.ultrasafe.local/intelligence/anm-storm-hail-warning',
        '2026-05-09T09:20:00+03:00',
        '2026-05-09T10:00:00+03:00',
        'ANM severe storm and hail warning for insured residential property',
        NULL,
        'ANM issued a public warning avertizare for severe storm and grindina conditions across several Romanian counties. The notice mentions potential damage to home locuinte roofs, fire response constraints after lightning, and expected daune claims for residential property insurance. Underwriters should monitor exposed renewals and open claims.',
        '[]'::jsonb,
        'demo-intel-storm-hail-warning-v1',
        'success',
        'success',
        NULL,
        '2026-05-09T10:00:00+03:00'
    ),
    (
        '90000000-0000-0000-0000-000000000003',
        'demo_intel',
        'https://demo.ultrasafe.local/intelligence/paid-flood-premium-report',
        'https://demo.ultrasafe.local/intelligence/paid-flood-premium-report',
        '2026-05-09T09:40:00+03:00',
        '2026-05-09T10:00:00+03:00',
        'PAID report on flood exposure and PAD premium affordability',
        NULL,
        'PAID released a market report raport on flood inundatii exposure for PAD and home insurance portfolios. The report discusses premium prima affordability, coverage uptake for locuinte, and flood risk concentration in Romanian residential property. Pricing and appetite assumptions may need review for affected counties.',
        '[]'::jsonb,
        'demo-intel-flood-premium-report-v1',
        'success',
        'success',
        NULL,
        '2026-05-09T10:00:00+03:00'
    )
ON CONFLICT (source_id, canonical_url) DO UPDATE SET
    original_url = EXCLUDED.original_url,
    published_at = EXCLUDED.published_at,
    fetched_at = EXCLUDED.fetched_at,
    title = EXCLUDED.title,
    raw_html = EXCLUDED.raw_html,
    extracted_text = EXCLUDED.extracted_text,
    attachments_json = EXCLUDED.attachments_json,
    content_hash = EXCLUDED.content_hash,
    fetch_status = EXCLUDED.fetch_status,
    parse_status = EXCLUDED.parse_status,
    error_message = EXCLUDED.error_message,
    created_at = EXCLUDED.created_at;

