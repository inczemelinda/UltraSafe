from __future__ import annotations

from datetime import datetime, timezone

import pytest
from psycopg.types.json import Jsonb

from underwright.domain.wording import WordingDocumentCreate
from underwright.infrastructure.postgres.wording_document_repository import (
    PostgresWordingDocumentRepository,
)


def test_wording_repository_creates_document_with_json_metadata() -> None:
    cursor = FakeCursor(
        fetchone_rows=[
            {
                "id": 1,
                "code": "DEMO_PAD_POLICY_WORDING_RO",
                "title": "PAD Property Insurance Wording RO",
                "product_line": "property",
                "jurisdiction": "RO",
                "language": "ro-RO",
                "insurer_id": None,
                "status": "published",
                "metadata_json": {"is_synthetic": True},
                "created_at": _now(),
                "updated_at": _now(),
            }
        ]
    )
    repo = PostgresWordingDocumentRepository(make_connection_factory(cursor))

    result = repo.create_wording_document(
        WordingDocumentCreate(
            code="DEMO_PAD_POLICY_WORDING_RO",
            title="PAD Property Insurance Wording RO",
            product_line="property",
            jurisdiction="RO",
            language="ro-RO",
            status="published",
            metadata_json={"is_synthetic": True},
        )
    )

    assert result.code == "DEMO_PAD_POLICY_WORDING_RO"
    assert cursor.connection.committed is True
    assert isinstance(cursor.executed[0][1][-1], Jsonb)


def test_wording_repository_rejects_published_version_text_update() -> None:
    cursor = FakeCursor(fetchone_rows=[{"status": "published"}])
    repo = PostgresWordingDocumentRepository(make_connection_factory(cursor))

    with pytest.raises(ValueError, match="Published wording versions are immutable"):
        repo.update_wording_version_full_text(
            10,
            full_text="Changed legal terms",
            content_hash="changed-hash",
        )

    assert cursor.connection.committed is False
    assert len(cursor.executed) == 1


def test_wording_repository_current_published_version_returns_none_when_missing() -> None:
    cursor = FakeCursor(fetchone_rows=[None])
    repo = PostgresWordingDocumentRepository(make_connection_factory(cursor))

    result = repo.get_current_published_version(1)

    assert result is None


class FakeCursor:
    def __init__(self, fetchone_rows: list[dict | None] | None = None) -> None:
        self.fetchone_rows = list(fetchone_rows or [])
        self.executed: list[tuple[str, object]] = []
        self.connection = FakeConnection(self)

    def execute(self, sql: str, params=()) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self, row_factory=None):
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def make_connection_factory(cursor: FakeCursor):
    def factory():
        return cursor.connection

    return factory


def _now() -> datetime:
    return datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
