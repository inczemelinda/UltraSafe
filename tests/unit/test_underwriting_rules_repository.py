from __future__ import annotations

from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from underwright.infrastructure.postgres.underwriting_rules_repository import (
    DEFAULT_RULES_CONTENT,
    DOCUMENT_KEY,
    PostgresUnderwritingRulesRepository,
)


class FakeCursor:
    def __init__(self, fetchone_rows: list[dict | None]) -> None:
        self.fetchone_rows = list(fetchone_rows)
        self.executed: list[tuple[str, object | None]] = []

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

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


def make_connection_factory(cursor: FakeCursor):
    connection = FakeConnection(cursor)

    def factory():
        return connection

    return factory, connection


def test_default_underwriting_rules_are_backend_configured() -> None:
    section_ids = [section["id"] for section in DEFAULT_RULES_CONTENT["sections"]]

    assert DEFAULT_RULES_CONTENT["key"] == DOCUMENT_KEY
    assert section_ids == [
        "quote_review_principles",
        "premium_calculation_model",
        "manual_review_rules",
        "underwriting_questions",
        "coverage_and_limits",
        "claim_review_rules",
    ]
    assert "Final score <= 70" in str(DEFAULT_RULES_CONTENT)


def test_repository_inserts_default_rules_when_database_has_no_document() -> None:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    seeded_row = {
        "document_key": DOCUMENT_KEY,
        "content_json": DEFAULT_RULES_CONTENT,
        "updated_at": now,
        "updated_by": None,
    }
    cursor = FakeCursor(fetchone_rows=[None, seeded_row])
    connection_factory, connection = make_connection_factory(cursor)
    repository = PostgresUnderwritingRulesRepository(connection_factory)

    document = repository.get_document()

    assert document.key == DOCUMENT_KEY
    assert [section.id for section in document.sections] == [
        "quote_review_principles",
        "premium_calculation_model",
        "manual_review_rules",
        "underwriting_questions",
        "coverage_and_limits",
        "claim_review_rules",
    ]
    assert connection.committed is True
    insert_sql, insert_params = cursor.executed[-1]
    assert "INSERT INTO underwriting_rules_document" in insert_sql
    assert insert_params[0] == DOCUMENT_KEY
    assert isinstance(insert_params[1], Jsonb)
