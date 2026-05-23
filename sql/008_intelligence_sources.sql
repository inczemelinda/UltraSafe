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
        'asf_ro',
        'ASF Romania',
        'RO',
        'regulator',
        'authoritative',
        'web_scrape',
        'ro',
        TRUE,
        '{
            "list_url":"https://asfromania.ro/ro/a/100/comunicate",
            "max_items":20,
            "allowed_path_fragments":["comunicate"],
            "blocked_path_fragments":["/ro/a/100/comunicate","/consumatori","/despre-asf"],
            "blocked_title_fragments":["Autoritatea de Supraveghere Financiara","Autoritatea de Supraveghere Financiară","Consumatori"],
            "min_text_chars":250,
            "required_text_fragments":["asigur","pad","locuin","cutremur","inunda","incend","furtun","grindin","daun","prima","solvabil"]
        }'::jsonb,
        '2026-05-06T10:00:00+03:00',
        '2026-05-06T10:00:00+03:00'
    ),
    (
        'paid_ro',
        'PAID Romania',
        'RO',
        'insurance_pool',
        'authoritative',
        'web_scrape',
        'ro',
        TRUE,
        '{
            "list_url":"https://www.paidromania.ro/comunicate/",
            "max_items":5,
            "allowed_path_fragments":["comunicate"],
            "blocked_title_fragments":["Comunicate","PAID Romania"],
            "min_text_chars":180,
            "required_text_fragments":["pad","locuin","cutremur","inunda","prima","despagub"]
        }'::jsonb,
        '2026-05-06T10:00:00+03:00',
        '2026-05-06T10:00:00+03:00'
    ),
    (
        'anm_ro',
        'Administratia Nationala de Meteorologie',
        'RO',
        'weather',
        'authoritative',
        'web_scrape',
        'ro',
        TRUE,
        '{
            "list_url":"https://www.meteoromania.ro/avertizari-/",
            "max_items":5,
            "allowed_path_fragments":["avertizari","informari"],
            "blocked_title_fragments":["Administratia Nationala de Meteorologie","Administrația Națională de Meteorologie"],
            "min_text_chars":120,
            "required_text_fragments":["avertizare","cod","furtun","grindin","vijelie","ploi","inund"]
        }'::jsonb,
        '2026-05-06T10:00:00+03:00',
        '2026-05-06T10:00:00+03:00'
    ),
    (
        'infp_ro',
        'Institutul National pentru Fizica Pamantului',
        'RO',
        'seismic_data',
        'authoritative',
        'web_scrape',
        'ro',
        TRUE,
        '{
            "list_url":"https://www.infp.ro/index.php",
            "max_items":5,
            "allowed_path_fragments":["cutremur","seismic","earthquake","event","index.php"],
            "blocked_path_fragments":["?i=con","?i=des","?i=doc","?i=int","?i=org"],
            "blocked_title_fragments":["Institutul National pentru Fizica Pamantului","Institutul Național pentru Fizica Pământului","INCDFP - Conducere","INCDFP - Informatii de interes public","INCDFP - Informaţii de interes public","INCDFP - Integritate","INCDFP - Organigrama"],
            "min_text_chars":120,
            "required_text_fragments":["cutremur","seismic","magnitudine","adancime"]
        }'::jsonb,
        '2026-05-06T10:00:00+03:00',
        '2026-05-06T10:00:00+03:00'
    ),
    (
        'ancpi_open_data_arcgis',
        'ANCPI Open Data Hub',
        'RO',
        'cadastral_data',
        'authoritative',
        'api',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://open-data-ancpi.hub.arcgis.com/",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires ArcGIS Hub dataset discovery and layer download connector before enabling.",
            "reference_use":"cadastral and geospatial property enrichment"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'osm_nominatim_policy',
        'OpenStreetMap Nominatim Usage Policy',
        'RO',
        'geospatial_data',
        'trusted',
        'manual',
        'en',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://operations.osmfoundation.org/policies/nominatim/",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Policy reference for any future Nominatim geocoding adapter; not a data feed.",
            "reference_use":"geocoding policy and rate-limit constraints"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'eurostat_gisco_nuts',
        'Eurostat GISCO NUTS geodata',
        'RO',
        'geospatial_data',
        'authoritative',
        'api',
        'en',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires GISCO/NUTS geodata download and geometry normalization connector before enabling.",
            "reference_use":"NUTS territorial boundary enrichment"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'localapi_ro_address',
        'LocalAPI Romania Address Service',
        'RO',
        'address_data',
        'trusted',
        'api',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://localapi.ro/services/address/",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires address lookup/geocoding adapter and API usage review before enabling.",
            "reference_use":"Romanian address normalization and administrative-unit lookup"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'rowater_flood_cycle2',
        'Romania flood hazard map cycle 2',
        'RO',
        'flood_hazard',
        'authoritative',
        'manual',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://harticiclul2.inundatii.ro/map@45.9891990,23.4491860,7z",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires web-map/layer extraction connector before enabling.",
            "reference_use":"flood hazard and risk layers"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'olt_rowater_flood_maps',
        'ABA Olt flood hazard and risk maps',
        'RO',
        'flood_hazard',
        'authoritative',
        'web_scrape',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "detail_urls":["https://olt.rowater.ro/activitatea-institutiei/structuri/managementul-situatiilor-de-urgenta/directiva-inundatii-2007-60-ce/harti-de-hazard-si-risc-la-inundatii/"],
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires document/link extraction strategy before enabling.",
            "reference_use":"regional flood hazard and risk map references"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'worldbank_ro_flood_maps',
        'World Bank Romania flood map development case study',
        'RO',
        'flood_hazard',
        'trusted',
        'web_scrape',
        'en',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "detail_urls":["https://www.worldbank.org/en/results/2023/03/22/-flood-hazard-and-risk-maps-development-and-use-of-flood-maps-to-strengthen-integrated-flood-risk-management-in-romania"],
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Reference narrative source; enable only if used for documentation/evidence extraction.",
            "reference_use":"context for Romanian flood hazard map development and usage"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'infp_lab_seismic',
        'INFP seismology laboratory data',
        'RO',
        'seismic_data',
        'authoritative',
        'web_scrape',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "detail_urls":["https://infp.ro/index.php?i=lab1"],
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires seismic reference parser before enabling.",
            "reference_use":"seismology source metadata and seismic hazard context"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'mdlpa_seismic_observator',
        'MDLPA seismic observatory map',
        'RO',
        'seismic_hazard',
        'authoritative',
        'manual',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://observator.mdlpa.ro/portal/apps/webappviewer/index.html?id=ceab6fd501124bcaaa701a8e2baf6a36",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires ArcGIS/web-map layer extraction connector before enabling.",
            "reference_use":"seismic hazard/geospatial enrichment"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'amccrs_pmb_seismic_buildings',
        'AMCCRS PMB seismic-risk buildings list',
        'RO',
        'building_seismic_risk',
        'authoritative',
        'web_scrape',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "detail_urls":["https://amccrs-pmb.ro/lista-imobile-2/"],
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires table/document extraction connector before enabling.",
            "reference_use":"building-level seismic risk enrichment for Bucharest"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'copernicus_sentinel_dem',
        'Copernicus Sentinel Hub DEM',
        'RO',
        'climate_data',
        'authoritative',
        'api',
        'en',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires Copernicus/Sentinel Hub adapter and credentials before enabling.",
            "reference_use":"digital elevation model enrichment"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'copernicus_cds_datasets',
        'Copernicus Climate Data Store datasets',
        'RO',
        'climate_data',
        'authoritative',
        'api',
        'en',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://cds.climate.copernicus.eu/datasets",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires CDS API adapter and dataset selection before enabling.",
            "reference_use":"climate and weather-history enrichment"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'anm_inspire_climate_record',
        'ANM INSPIRE climate geonetwork record',
        'RO',
        'climate_data',
        'authoritative',
        'api',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://inspire.meteoromania.ro/geonetwork/srv/api/records/b90bef90-b3f9-4a3e-aff3-f86c1c49a6e3",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires GeoNetwork metadata/API connector before enabling.",
            "reference_use":"ANM climate/geospatial metadata"
        }'::jsonb,
        '2026-05-09T10:00:00+03:00',
        '2026-05-09T10:00:00+03:00'
    ),
    (
        'data_gov_ro_tempo',
        'Data.gov.ro TEMPO statistical database',
        'RO',
        'statistical_data',
        'authoritative',
        'api',
        'ro',
        FALSE,
        '{
            "pipeline_domain":"risk_reference",
            "source_url":"https://data.gov.ro/dataset/baza-de-date-statistice-tempo",
            "ingestion_status":"registered_pending_connector",
            "activation_note":"Requires CKAN/API and TEMPO dataset connector before enabling.",
            "reference_use":"Romanian statistical enrichment"
        }'::jsonb,
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
