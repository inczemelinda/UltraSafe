from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from underwright.legal_demo_seed.cli import (
    DATASET,
    LegalDemoSeedResult,
    build_parser,
    main,
    seed_legal_demo_data,
)


ROOT = Path(__file__).resolve().parents[2]


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params=()) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        return {"id": 42}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor
        self.committed = False

    def cursor(self, row_factory=None):
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_seed_legal_demo_command_parser_accepts_dataset_and_reset() -> None:
    args = build_parser().parse_args(["--dataset", DATASET, "--reset"])

    assert args.dataset == DATASET
    assert args.reset is True


def test_seed_legal_demo_data_resets_and_seeds_law_change_workflow() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    result = seed_legal_demo_data(
        lambda: connection,
        dataset=DATASET,
        reset=True,
    )

    sql_text = "\n".join(sql for sql, _ in cursor.executed)
    assert result == LegalDemoSeedResult(
        dataset=DATASET,
        reset=True,
        sources=1,
        raw_items=1,
        legal_documents=1,
        events=1,
        templates=1,
        review_candidates=1,
    )
    assert connection.committed is True
    assert "DELETE FROM template_draft_revision" in sql_text
    assert "DELETE FROM template_change_suggestion" in sql_text
    assert "DELETE FROM legal_document_template_review_candidate" in sql_text
    assert "DELETE FROM intelligence_template_review_candidate" in sql_text
    assert "DELETE FROM external_event" in sql_text
    assert "DELETE FROM template" in sql_text
    assert "DELETE FROM normalized_legal_document" in sql_text
    assert "INSERT INTO normalized_legal_document" in sql_text
    assert "INSERT INTO external_event" in sql_text
    assert "INSERT INTO template" in sql_text
    assert "INSERT INTO legal_document_template_review_candidate" in sql_text
    assert "ON CONFLICT (raw_item_id) DO UPDATE" in sql_text
    assert "normalized_legal_document_id" in sql_text
    params_text = "\n".join(str(params) for _, params in cursor.executed)
    assert "amended_reference" in params_text
    assert "needs_review" in params_text
    assert "DEMO - Parlamentul României" in params_text
    assert "DEMO - Monitorul Oficial nr. 500/2026" in params_text
    assert "ro:lege:99:2026" in params_text
    assert "ro:lege:260:2008" in params_text
    assert "5 zile calendaristice" in params_text
    assert "10 zile calendaristice" in params_text
    assert any(params == (DATASET,) for _, params in cursor.executed)
    assert any(params == (DATASET, DATASET) for _, params in cursor.executed)
    assert any(
        params == (DATASET, DATASET, DATASET)
        for _, params in cursor.executed
    )
    assert any(params == (f"demo://{DATASET}/%",) for _, params in cursor.executed)


def test_seed_legal_demo_data_rejects_unknown_dataset() -> None:
    with pytest.raises(ValueError, match="Unsupported legal demo dataset"):
        seed_legal_demo_data(lambda: FakeConnection(FakeCursor()), dataset="unknown")


def test_seed_legal_demo_main_prints_summary() -> None:
    seeded = LegalDemoSeedResult(
        dataset=DATASET,
        reset=True,
        sources=1,
        raw_items=1,
        legal_documents=1,
        events=1,
        templates=1,
        review_candidates=1,
    )

    with patch(
        "underwright.legal_demo_seed.cli.seed_legal_demo_data",
        return_value=seeded,
    ) as seed:
        with patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            result = main(["--dataset", DATASET, "--reset"])

    assert result == 0
    assert seed.call_args.kwargs == {"dataset": DATASET, "reset": True}
    output = fake_stdout.getvalue()
    assert f"dataset={DATASET}" in output
    assert "legal_documents=1" in output
    assert "review_candidates=1" in output


def test_seed_legal_demo_command_is_registered_and_does_not_import_ai_or_network() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    source = (ROOT / "src/underwright/legal_demo_seed/cli.py").read_text()

    assert 'seed-legal-demo-data = "underwright.legal_demo_seed.cli:main"' in pyproject
    for blocked in [
        "underwright.infrastructure.llm",
        "OpenAI",
        "httpx",
        "requests",
        "urllib",
    ]:
        assert blocked not in source


def test_legal_demo_template_metadata_migration_is_wired() -> None:
    migration = (ROOT / "sql/012_legal_demo_template_metadata.sql").read_text()
    candidate_migration = (
        ROOT / "sql/013_legal_document_template_review_candidates.sql"
    ).read_text()
    migrate_script = (ROOT / "scripts/db_migrate.sh").read_text()

    assert "ADD COLUMN IF NOT EXISTS jurisdiction" in migration
    assert "ADD COLUMN IF NOT EXISTS product_line" in migration
    assert "ADD COLUMN IF NOT EXISTS legal_references_json" in migration
    assert "ADD COLUMN IF NOT EXISTS metadata_json" in migration
    assert "intelligence_template_review_candidate_demo_dataset_idx" in migration
    assert "legal_document_template_review_candidate" in candidate_migration
    assert "sql/012_legal_demo_template_metadata.sql" in migrate_script
    assert "sql/013_legal_document_template_review_candidates.sql" in migrate_script
