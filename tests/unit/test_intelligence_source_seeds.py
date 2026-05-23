from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from underwright.domain.intelligence import Source


ROOT = Path(__file__).resolve().parents[2]


def test_demo_seed_includes_initial_external_sources() -> None:
    seed_sql = Path("sql/008_intelligence_sources.sql").read_text()

    for source_id in [
        "asf_ro",
        "paid_ro",
        "anm_ro",
        "infp_ro",
        "ancpi_open_data_arcgis",
        "osm_nominatim_policy",
        "eurostat_gisco_nuts",
        "localapi_ro_address",
        "rowater_flood_cycle2",
        "olt_rowater_flood_maps",
        "worldbank_ro_flood_maps",
        "infp_lab_seismic",
        "mdlpa_seismic_observator",
        "amccrs_pmb_seismic_buildings",
        "copernicus_sentinel_dem",
        "copernicus_cds_datasets",
        "anm_inspire_climate_record",
        "data_gov_ro_tempo",
    ]:
        assert f"'{source_id}'" in seed_sql

    for source_url in [
        "https://www.paidromania.ro/comunicate/",
        "https://www.meteoromania.ro/avertizari-/",
        "https://www.infp.ro/index.php",
        "https://open-data-ancpi.hub.arcgis.com/",
        "https://operations.osmfoundation.org/policies/nominatim/",
        "https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics",
        "https://localapi.ro/services/address/",
        "https://harticiclul2.inundatii.ro/map@45.9891990,23.4491860,7z",
        "https://olt.rowater.ro/activitatea-institutiei/structuri/managementul-situatiilor-de-urgenta/directiva-inundatii-2007-60-ce/harti-de-hazard-si-risc-la-inundatii/",
        "https://www.worldbank.org/en/results/2023/03/22/-flood-hazard-and-risk-maps-development-and-use-of-flood-maps-to-strengthen-integrated-flood-risk-management-in-romania",
        "https://infp.ro/index.php?i=lab1",
        "https://observator.mdlpa.ro/portal/apps/webappviewer/index.html?id=ceab6fd501124bcaaa701a8e2baf6a36",
        "https://amccrs-pmb.ro/lista-imobile-2/",
        "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html",
        "https://cds.climate.copernicus.eu/datasets",
        "https://inspire.meteoromania.ro/geonetwork/srv/api/records/b90bef90-b3f9-4a3e-aff3-f86c1c49a6e3",
        "https://data.gov.ro/dataset/baza-de-date-statistice-tempo",
    ]:
        assert source_url in seed_sql


def test_reference_data_sources_are_registered_pending_connectors() -> None:
    seed_sql = Path("sql/008_intelligence_sources.sql").read_text()

    assert seed_sql.count('"pipeline_domain":"risk_reference"') == 14
    assert seed_sql.count('"ingestion_status":"registered_pending_connector"') == 14
    assert '"pipeline_domain":"legal_documents"' not in seed_sql


def test_demo_seed_includes_source_quality_config() -> None:
    seed_sql = Path("sql/008_intelligence_sources.sql").read_text()

    assert "blocked_path_fragments" in seed_sql
    assert "blocked_title_fragments" in seed_sql
    assert "min_text_chars" in seed_sql
    assert "required_text_fragments" in seed_sql
    assert "/ro/a/100/comunicate" in seed_sql
    assert "Autoritatea de Supraveghere Financiară" in seed_sql
    assert "?i=con" in seed_sql
    assert "?i=des" in seed_sql
    assert "INCDFP - Conducere" in seed_sql


def test_legal_document_seed_adds_disabled_official_sources() -> None:
    seed_sql = (ROOT / "sql/010_legal_document_sources.sql").read_text()

    assert seed_sql.count('"pipeline_domain":"legal_documents"') == 2
    assert "'ro_portal_legislativ'" in seed_sql
    assert '"parser_id":"ro_portal_legislativ"' in seed_sql
    assert '"extractor_id":"legislatie_just"' in seed_sql
    assert '"jurisdiction":"RO"' in seed_sql
    assert '"authority_type":"official_legal_portal"' in seed_sql
    assert '"source_url":"https://legislatie.just.ro/"' in seed_sql
    assert '"max_pages":1' in seed_sql
    assert "'eu_eurlex_oj_l_series'" in seed_sql
    assert '"parser_id":"eu_eurlex_oj"' in seed_sql
    assert '"jurisdiction":"EU"' in seed_sql
    assert '"authority_type":"official_journal"' in seed_sql
    assert seed_sql.count("'web_scrape'") == 2
    assert seed_sql.count("FALSE") == 2
    assert "accepted_document_types" in seed_sql
    assert "minimum_normalization_requirements" in seed_sql
    assert "allowed_url_patterns" in seed_sql
    assert "blocked_url_patterns" in seed_sql
    assert "external_event" not in seed_sql


def test_legal_document_sources_are_wired_into_demo_seed_script() -> None:
    seed_script = (ROOT / "scripts/db_seed_demo.sh").read_text()

    assert "sql/010_legal_document_sources.sql" in seed_script


def test_source_model_accepts_disabled_eu_legal_document_source() -> None:
    now = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)

    source = Source(
        source_id="eu_eurlex_oj_l_series",
        name="EUR-Lex Official Journal L series",
        country="EU",
        source_type="official_journal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="en",
        enabled=False,
        config_json={
            "pipeline_domain": "legal_documents",
            "parser_id": "eu_eurlex_oj",
        },
        created_at=now,
        updated_at=now,
    )

    assert source.connector_type == "web_scrape"
    assert source.config_json["parser_id"] == "eu_eurlex_oj"
