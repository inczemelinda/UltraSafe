from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_demo_intelligence_seed_adds_raw_pipeline_inputs() -> None:
    seed_sql = (ROOT / "sql/009_demo_intelligence_events.sql").read_text()

    assert "'demo_intel'" in seed_sql
    assert "INSERT INTO raw_source_item" in seed_sql
    assert seed_sql.count("'demo_intel'") >= 4
    assert seed_sql.count("'90000000-0000-0000-0000-00000000000") == 3
    assert "ON CONFLICT (source_id, canonical_url) DO UPDATE" in seed_sql


def test_demo_intelligence_seed_uses_relevant_property_terms() -> None:
    seed_sql = (ROOT / "sql/009_demo_intelligence_events.sql").read_text().lower()

    expected_terms = [
        "pad",
        "locuinte",
        "earthquake",
        "cutremur",
        "storm",
        "grindina",
        "flood",
        "inundatii",
        "premium",
        "coverage",
        "clauze",
    ]

    for term in expected_terms:
        assert term in seed_sql


def test_demo_intelligence_seed_is_wired_into_demo_seed_script() -> None:
    seed_script = (ROOT / "scripts/db_seed_demo.sh").read_text()

    assert "sql/010_legal_document_sources.sql" in seed_script
    assert "sql/009_demo_intelligence_events.sql" in seed_script
