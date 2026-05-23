BEGIN;

TRUNCATE TABLE
    generated_document,
    quote_acceptance,
    quote_document,
    quote_request,
    pricing,
    risk_factor,
    risk_profile,
    contract,
    insured_asset,
    customer,
    insurer,
    template,
    address
RESTART IDENTITY CASCADE;

INSERT INTO address (
    country,
    county,
    city,
    street,
    number,
    postal_code,
    full_text
)
VALUES
    (
        'Romania',
        'Bucuresti',
        'Bucuresti',
        'Bd. Exemplu',
        '100',
        '010101',
        'Bd. Exemplu 100, Bucuresti'
    ),
    (
        'Romania',
        'Bucuresti',
        'Bucuresti',
        'Str. Lalelelor',
        '12',
        '031234',
        'Str. Lalelelor 12, Sector 3, Bucuresti'
    );

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
VALUES (
    'individual',
    'Ana Popescu',
    '1900101123456',
    NULL,
    'ana.popescu@client.com',
    '+40 700 111 222',
    (SELECT id FROM address WHERE full_text = 'Str. Lalelelor 12, Sector 3, Bucuresti'),
    NOW(),
    NOW(),
    'seed',
    1
);

INSERT INTO insurer (
    name,
    company_id,
    representative_name,
    representative_role,
    address_id
)
VALUES (
    'Asigurator Demo SA',
    'RO12345678',
    'Mihai Ionescu',
    'Director General',
    (SELECT id FROM address WHERE full_text = 'Bd. Exemplu 100, Bucuresti')
);

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
VALUES (
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu'),
    'apartment',
    'residential',
    'concrete',
    1986,
    4,
    68.00,
    350000.00,
    'owner_occupied',
    2,
    (SELECT id FROM address WHERE full_text = 'Str. Lalelelor 12, Sector 3, Bucuresti'),
    '2026-04-20T10:00:00+03:00',
    '2026-04-20T10:00:00+03:00'
);

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
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu'),
    'approved',
    jsonb_build_object(
        'type', 'individual',
        'full_name', 'Ana Popescu',
        'national_id', '1900101123456',
        'email', 'ana.popescu@client.com',
        'phone', '+40 700 111 222',
        'address', 'Str. Lalelelor 12, Sector 3, Bucuresti'
    ),
    jsonb_build_object(
        'asset_type', 'apartment',
        'usage_type', 'residential',
        'construction_type', 'concrete',
        'year_built', 1986,
        'floor', 4,
        'area_sqm', 68.00,
        'declared_value', 350000.00,
        'occupancy', 'owner_occupied',
        'previous_claims_count', 2,
        'address', jsonb_build_object(
            'country', 'Romania',
            'county', 'Bucuresti',
            'city', 'Bucuresti',
            'street', 'Str. Lalelelor',
            'number', '12',
            'postal_code', '031234',
            'full_text', 'Str. Lalelelor 12, Sector 3, Bucuresti'
        )
    ),
    '[{"step":"seed","value":"Demo source quote for PAD-RISK-2026-000145."}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":1200,"final_premium":1368},"request_details":{"coverage_amount":350000,"security_features":["Alarm"]}}'::jsonb,
    '2026-04-20T10:00:00+03:00',
    '2026-04-20T10:00:00+03:00'
),
(
    '11111111-1111-4111-8111-000000000005',
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu'),
    'auto_accepted',
    jsonb_build_object(
        'type', 'individual',
        'full_name', 'Ana Popescu',
        'national_id', '1900101123456',
        'email', 'ana.popescu@client.com',
        'phone', '+40 700 111 222',
        'address', 'Str. Lalelelor 12, Sector 3, Bucuresti'
    ),
    jsonb_build_object(
        'asset_type', 'apartment',
        'usage_type', 'residential',
        'construction_type', 'concrete',
        'year_built', 1986,
        'floor', 4,
        'area_sqm', 68.00,
        'declared_value', 350000.00,
        'occupancy', 'owner_occupied',
        'previous_claims_count', 2,
        'address', jsonb_build_object(
            'country', 'Romania',
            'county', 'Bucuresti',
            'city', 'Bucuresti',
            'street', 'Str. Lalelelor',
            'number', '12',
            'postal_code', '031234',
            'full_text', 'Str. Lalelelor 12, Sector 3, Bucuresti'
        )
    ),
    '[{"step":"seed","value":"Demo source quote for PAD-PROPERTY-2026-000150."}]'::jsonb,
    '{"is_complete":true,"missing_fields":[]}'::jsonb,
    '[]'::jsonb,
    '{"pricing":{"base_premium":980,"final_premium":1117.20},"request_details":{"coverage_amount":350000,"security_features":["Smoke detector"]}}'::jsonb,
    '2026-04-25T10:00:00+03:00',
    '2026-04-25T10:00:00+03:00'
);

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
    created_at,
    updated_at
)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    'PAD-RISK-2026-000145',
    'insurance_contract',
    '1.0',
    (SELECT id FROM insurer WHERE name = 'Asigurator Demo SA'),
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu'),
    (
        SELECT id
        FROM insured_asset
        WHERE customer_id = (SELECT id FROM customer WHERE full_name = 'Ana Popescu')
        LIMIT 1
    ),
    '2026-04-20',
    '2026-05-01',
    '2027-04-30',
    'Romania',
    'Legea 260/2008',
    'RON',
    'draft',
    '11111111-1111-4111-8111-000000000001',
    '2026-04-20T10:00:00+03:00',
    '2026-04-20T10:00:00+03:00'
),
(
    '10000000-0000-0000-0000-000000000002',
    'PAD-PROPERTY-2026-000150',
    'insurance_contract',
    '1.0',
    (SELECT id FROM insurer WHERE name = 'Asigurator Demo SA'),
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu'),
    (
        SELECT id
        FROM insured_asset
        WHERE customer_id = (SELECT id FROM customer WHERE full_name = 'Ana Popescu')
        LIMIT 1
    ),
    '2026-04-25',
    '2026-05-10',
    '2027-05-09',
    'Romania',
    'Legea 260/2008',
    'RON',
    'draft',
    '11111111-1111-4111-8111-000000000005',
    '2026-04-25T10:00:00+03:00',
    '2026-04-25T10:00:00+03:00'
);

INSERT INTO risk_profile (
    contract_id,
    overall_risk_level,
    risk_score,
    assessment_date,
    created_at
)
VALUES (
    (SELECT id FROM contract WHERE contract_number = 'PAD-RISK-2026-000145'),
    'medium_high',
    72,
    '2026-04-20',
    '2026-04-20T10:00:00+03:00'
),
(
    (SELECT id FROM contract WHERE contract_number = 'PAD-PROPERTY-2026-000150'),
    'medium',
    65,
    '2026-04-25',
    '2026-04-25T10:00:00+03:00'
);

INSERT INTO risk_factor (
    risk_profile_id,
    code,
    label,
    level,
    score,
    evidence_json,
    clause_tags_json,
    premium_adjustment_percent,
    deductible_adjustment_ron,
    created_at
)
VALUES
    (
        (
            SELECT rp.id
            FROM risk_profile rp
            JOIN contract c ON c.id = rp.contract_id
            WHERE c.contract_number = 'PAD-RISK-2026-000145'
        ),
        'FLOOD_EXPOSURE',
        'Expunere la inundatii',
        'high',
        85,
        '["zona cu istoric de inundatii", "proximitate fata de zona vulnerabila"]'::jsonb,
        '["flood_specific", "inspection_recommended"]'::jsonb,
        12.00,
        500.00,
        '2026-04-20T10:00:00+03:00'
    ),
    (
        (
            SELECT rp.id
            FROM risk_profile rp
            JOIN contract c ON c.id = rp.contract_id
            WHERE c.contract_number = 'PAD-RISK-2026-000145'
        ),
        'EARTHQUAKE_EXPOSURE',
        'Expunere la cutremur',
        'medium',
        63,
        '["an constructie 1986", "oras cu expunere seismica relevanta"]'::jsonb,
        '["earthquake_standard_plus"]'::jsonb,
        5.00,
        250.00,
        '2026-04-20T10:00:00+03:00'
    ),
    (
        (
            SELECT rp.id
            FROM risk_profile rp
            JOIN contract c ON c.id = rp.contract_id
            WHERE c.contract_number = 'PAD-RISK-2026-000145'
        ),
        'CLAIMS_HISTORY',
        'Istoric daune',
        'medium',
        58,
        '["2 daune raportate in ultimii 5 ani"]'::jsonb,
        '["claims_history_review"]'::jsonb,
        7.00,
        300.00,
        '2026-04-20T10:00:00+03:00'
    ),
    (
        (
            SELECT rp.id
            FROM risk_profile rp
            JOIN contract c ON c.id = rp.contract_id
            WHERE c.contract_number = 'PAD-PROPERTY-2026-000150'
        ),
        'PROPERTY_AGE',
        'Vârsta proprietății',
        'low',
        40,
        '["an constructie 1986, dar bine intretinuta"]'::jsonb,
        '["standard"]'::jsonb,
        3.00,
        0.00,
        '2026-04-25T10:00:00+03:00'
    );

INSERT INTO pricing (
    contract_id,
    base_premium_ron,
    adjustments_json,
    final_premium_ron
    ,
    payment_plan_type,
    installments
)
VALUES (
    (SELECT id FROM contract WHERE contract_number = 'PAD-RISK-2026-000145'),
    1200.00,
    '[
        {"source":"FLOOD_EXPOSURE","type":"percentage","value":12.00},
        {"source":"EARTHQUAKE_EXPOSURE","type":"percentage","value":5.00},
        {"source":"CLAIMS_HISTORY","type":"percentage","value":7.00}
    ]'::jsonb,
    1490.00,
    'annual',
    1
),
(
    (SELECT id FROM contract WHERE contract_number = 'PAD-PROPERTY-2026-000150'),
    1000.00,
    '[
        {"source":"PROPERTY_AGE","type":"percentage","value":3.00}
    ]'::jsonb,
    1030.00,
    'annual',
    1
);

INSERT INTO auth_user (
    email,
    password_hash,
    role,
    full_name,
    is_active
)
VALUES
(
    'maria.tiuca@ultrasafe.ro',
    '$2b$12$B79k1qxklI4HDn04r4AZbO3NPXsDGy7qjcDTmAs5FH1zZRhuN2Cgy',
    'underwriter',
    'Maria Tiuca',
    TRUE
),
(
    'melinda.incze@ultrasafe.ro',
    '$2b$12$B79k1qxklI4HDn04r4AZbO3NPXsDGy7qjcDTmAs5FH1zZRhuN2Cgy',
    'underwriter',
    'Melinda Incze',
    TRUE
),
(
    'alex.vulcu@ultrasafe.ro',
    '$2b$12$B79k1qxklI4HDn04r4AZbO3NPXsDGy7qjcDTmAs5FH1zZRhuN2Cgy',
    'underwriter',
    'Vulcu Alex',
    TRUE
),
(
    'damian.bululete@ultrasafe.ro',
    '$2b$12$B79k1qxklI4HDn04r4AZbO3NPXsDGy7qjcDTmAs5FH1zZRhuN2Cgy',
    'underwriter',
    'Bululete Damian',
    TRUE
),
(
    'vladut.rad@ultrasafe.ro',
    '$2b$12$B79k1qxklI4HDn04r4AZbO3NPXsDGy7qjcDTmAs5FH1zZRhuN2Cgy',
    'underwriter',
    'Rad Vladut',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    full_name = EXCLUDED.full_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

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
    (SELECT id FROM customer WHERE full_name = 'Ana Popescu' LIMIT 1),
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
)
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    full_name = EXCLUDED.full_name,
    phone = EXCLUDED.phone,
    client_id = EXCLUDED.client_id,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

INSERT INTO template (
    template_code,
    name,
    version,
    document_type,
    is_active,
    content,
    created_at
)
VALUES (
    'PAD_STANDARD_RO',
    'PAD Standard RO',
    '1.0',
    'insurance_contract',
    TRUE,
    $$CONTRACT DE ASIGURARE PAD

Numar contract: {{ contract_meta.contract_id }}
Asigurator: {{ parties.insurer.name }}
Asigurat: {{ parties.insured.full_name }}
Adresa bun asigurat: {{ parties.insured.address }}
Prima finala: {{ pricing.final_premium_ron }} {{ contract_meta.currency }}

Text suplimentar generat:
{{ supplementary_text }}
$$,
    '2026-04-20T10:00:00+03:00'
);


INSERT INTO template (
    template_code,
    name,
    version,
    document_type,
    is_active,
    content,
    created_at
)
VALUES (
    'PAD_PROPERTY_RO',
    'Property Insurance RO',
    '1.0',
    'insurance_contract',
    TRUE,
    $$POLIȚĂ DE ASIGURARE A LOCUINȚEI ȘI BUNURILOR

LOCUINȚĂ ȘI BUNURI

Număr poliță: {{contract_meta.contract_id}}
Data emiterii: {{contract_meta.issue_date}}

Între:

1. ASIGURĂTORUL

Societatea de Asigurare {{parties.insurer.name}}, cu sediul în {{parties.insurer.address}}, înregistrată la {{parties.insurer.company_id}}, denumită în continuare „Asigurător".

și

2. ASIGURATUL

Nume și prenume: {{parties.insured.full_name}}
Telefon:{{parties.insured.phone}}
Email:{{parties.insured.email}}

denumit în continuare „Asigurat".


CAPITOLUL I – OBIECTUL ASIGURĂRII

Art. 1

Prin prezenta poliță, Asigurătorul se obligă să despăgubească Asiguratul pentru daunele produse bunurilor asigurate, ca urmare a producerii riscurilor acoperite prevăzute în contract.

Art. 2 – Bunuri asigurate

Sunt asigurate următoarele:

A. Clădire / Locuință

• tip imobil: {{insured_asset.asset_type}}
• adresă: {{insured_asset.address.street}} {{insured_asset.address.number}}, {{insured_asset.address.city}}, {{insured_asset.address.county}}, {{insured_asset.address.country}}, {{insured_asset.address.postal_code}}
• suprafață: {{insured_asset.area_sqm}} mp
• an construcție: {{insured_asset.year_built}}

B. Bunuri mobile

• mobilier
• electrocasnice
• echipamente electronice
• obiecte personale
• alte bunuri declarate


 CAPITOLUL II – RISCURI ACOPERITE

Art. 3

Asigurătorul acordă despăgubiri pentru daune produse direct de:

• incendiu
• explozie
• trăsnet
• furtună
• grindină
• inundație
• avarii accidentale la instalații
• cutremur (dacă este inclus suplimentar)
• furt prin efracție
• vandalism


CAPITOLUL III – EXCLUDERI

Art. 4

Nu sunt acoperite:

• daune provocate intenționat de Asigurat;
• uzura normală;
• defecte de construcție;
• război, revoltă sau acte teroriste;
• confiscări dispuse de autorități;
• deteriorări produse prin neîntreținerea imobilului.


CAPITOLUL IV – SUMA ASIGURATĂ

Art. 5

Suma asigurată totală este de {{coverage.total_sum_insured}} RON.

Aceasta este compusă din:
• suma asigurată pentru locuință: {{coverage.building_sum_insured}} RON;
• suma asigurată pentru bunuri mobile: {{coverage.contents_sum_insured}} RON.


CAPITOLUL V – PRIMA DE ASIGURARE

Art. 6

Prima totală de asigurare este de: {{pricing.final_premium_ron}} RON.

Plata se poate efectua:

integral;
în rate trimestriale/semestriale.

Neplata primei poate conduce la suspendarea sau încetarea poliței.

CAPITOLUL VI – PERIOADA DE ASIGURARE

Art. 7

Asigurarea este valabilă în perioada:

de la {{contract_meta.effective_date}}
până la {{contract_meta.expiration_date}}

ora 00:00 – ora 24:00.

CAPITOLUL VII – OBLIGAȚIILE ASIGURATULUI

Art. 8

Asiguratul are obligația:

• să întrețină bunurile în stare bună;
• să ia măsuri pentru limitarea pagubelor;
• să anunțe producerea evenimentului în maximum 48 ore;
• să permită constatarea daunelor.

CAPITOLUL VIII – CONSTATAREA ȘI DESPĂGUBIREA

Art. 9

În caz de daună, Asiguratul va transmite:

• notificarea evenimentului;
• fotografii;
• documente justificative;
• acte de proprietate;
• proces verbal de la Poliție (în caz de furt).

Art. 10

Despăgubirea se acordă în limita sumei asigurate și după evaluarea efectuată de Asigurător.

Termenul de plată al despăgubirii este de maximum {{pricing.payment_plan.installments}} zile de la aprobarea dosarului de daună.

CAPITOLUL IX – ÎNCETAREA CONTRACTULUI

Art. 11

Contractul încetează:

• la expirarea perioadei asigurate;
• prin reziliere;
• prin neplata primei;
• prin distrugerea totală a bunului asigurat.

CAPITOLUL X – DISPOZIȚII FINALE

Art. 12

Prezentul contract este guvernat de legislația română în vigoare.

Orice litigiu va fi soluționat pe cale amiabilă, iar în caz contrar de instanțele competente.


SEMNĂTURI

ASIGURĂTOR                                                                      ASIGURAT

Nume reprezentant: {{parties.insurer.representative.name}}                              Nume: {{parties.insured.full_name}}
Semnătură: {{parties.insurer.representative.name}}                                      Semnătură: {{parties.insured.full_name}}
$$,
    '2026-04-20T10:00:00+03:00'
);

INSERT INTO quote_document (
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
    '11111111-1111-4111-8111-000000000001',
    (SELECT id FROM template WHERE template_code = 'PAD_STANDARD_RO' ORDER BY id DESC LIMIT 1),
    'success',
    'Generated quote document for PAD-RISK-2026-000145.',
    '{"template_used":{"template_code":"PAD_STANDARD_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"seed"}'::jsonb,
    '/demo/quotes/PAD-RISK-2026-000145-quote.pdf',
    '2026-04-20T10:00:00+03:00',
    '2026-04-20T10:00:00+03:00'
),
(
    '11111111-1111-4111-8111-000000000005',
    (SELECT id FROM template WHERE template_code = 'PAD_PROPERTY_RO' ORDER BY id DESC LIMIT 1),
    'success',
    'Generated quote document for PAD-PROPERTY-2026-000150.',
    '{"template_used":{"template_code":"PAD_PROPERTY_RO","template_version":"1.0"},"document_type":"quote_document","generation_mode":"seed"}'::jsonb,
    '/demo/quotes/PAD-PROPERTY-2026-000150-quote.pdf',
    '2026-04-25T10:00:00+03:00',
    '2026-04-25T10:00:00+03:00'
);

UPDATE contract
SET source_quote_document_id = quote_document.id,
    updated_at = NOW()
FROM quote_document
WHERE contract.source_quote_request_id = quote_document.quote_request_id
  AND contract.contract_number IN (
      'PAD-RISK-2026-000145',
      'PAD-PROPERTY-2026-000150'
  );

COMMIT;


