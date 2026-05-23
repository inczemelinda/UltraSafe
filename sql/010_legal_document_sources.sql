CREATE INDEX IF NOT EXISTS intelligence_source_pipeline_domain_idx
    ON intelligence_source ((config_json->>'pipeline_domain'));

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
VALUES
    (
        'ro_portal_legislativ',
        'Portal Legislativ Romania',
        'RO',
        'legal_portal',
        'authoritative',
        'web_scrape',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"legal_documents",
            "parser_id":"ro_portal_legislativ",
            "extractor_id":"legislatie_just",
            "jurisdiction":"RO",
            "authority_type":"official_legal_portal",
            "purpose":"Romanian national legal acts, with Monitorul Oficial metadata extracted during parsing where available.",
            "source_url":"https://legislatie.just.ro/",
            "list_url":"https://legislatie.just.ro/",
            "detail_urls":[
                "https://legislatie.just.ro/Public/DetaliiDocument/176426",
                "https://legislatie.just.ro/Public/DetaliiDocument/257093",
                "https://legislatie.just.ro/Public/DetaliiDocument/305297",
                "https://legislatie.just.ro/Public/DetaliiDocument/278184",
                "https://legislatie.just.ro/Public/DetaliiDocument/304895"
            ],
            "max_items":20,
            "max_pages":1,
            "allowed_detail_hosts":["legislatie.just.ro"],
            "allowed_path_fragments":["/public/detaliidocument","/public/rezultatecautare"],
            "blocked_path_fragments":["/contact","/account","/static/"],
            "allowed_url_patterns":["^https://legislatie\\.just\\.ro/(public|Public)/DetaliiDocument/\\d+"],
            "blocked_url_patterns":["/Contact","/Account","/static/"],
            "accepted_document_types":["lege","ordonanta","ordonanta_de_urgenta","hotarare","ordin","norma","decizie","regulament"],
            "minimum_normalization_requirements":["document_title","document_type","jurisdiction","source_url","publication_or_issue_date","raw_text_or_html"],
            "ingestion_status":"registered_pending_enablement",
            "activation_note":"Disabled by default; enable after parser_id ro_portal_legislativ can normalize official legal document metadata."
        }'::jsonb,
        '2026-05-11T10:00:00+03:00',
        '2026-05-11T10:00:00+03:00'
    ),
    (
        'eu_eurlex_oj_l_series',
        'EUR-Lex Official Journal L series',
        'EU',
        'official_journal',
        'authoritative',
        'web_scrape',
        'en',
        FALSE,
        '{
            "pipeline_domain":"legal_documents",
            "parser_id":"eu_eurlex_oj",
            "jurisdiction":"EU",
            "authority_type":"official_journal",
            "purpose":"EU Official Journal L-series legal acts only.",
            "source_url":"https://eur-lex.europa.eu/oj/direct-access.html?locale=en",
            "list_url":"https://eur-lex.europa.eu/oj/direct-access.html?locale=en",
            "max_items":20,
            "allowed_detail_hosts":["eur-lex.europa.eu"],
            "allowed_path_fragments":["/oj/direct-access","/legal-content/"],
            "blocked_path_fragments":["/summary/","/eli-register/"],
            "allowed_url_patterns":["^https://eur-lex\\.europa\\.eu/legal-content/[A-Z]{2}/TXT/\\?uri=OJ:L:","^https://eur-lex\\.europa\\.eu/oj/direct-access"],
            "blocked_url_patterns":["OJ:C:","ojSeries=C","/summary/"],
            "accepted_document_types":["regulation","directive","decision","delegated_regulation","implementing_regulation","official_journal_l_series_act"],
            "minimum_normalization_requirements":["document_title","document_type","jurisdiction","source_url","oj_series","oj_publication_date","celex_or_oj_reference"],
            "ingestion_status":"registered_pending_enablement",
            "activation_note":"Disabled by default; enable after parser_id eu_eurlex_oj can restrict normalization to Official Journal L-series acts."
        }'::jsonb,
        '2026-05-11T10:00:00+03:00',
        '2026-05-11T10:00:00+03:00'
    )
ON CONFLICT (source_id) DO UPDATE SET
    name = EXCLUDED.name,
    country = EXCLUDED.country,
    source_type = EXCLUDED.source_type,
    trust_tier = EXCLUDED.trust_tier,
    connector_type = EXCLUDED.connector_type,
    language = EXCLUDED.language,
    enabled = EXCLUDED.enabled,
    config_json = EXCLUDED.config_json,
    updated_at = EXCLUDED.updated_at;
