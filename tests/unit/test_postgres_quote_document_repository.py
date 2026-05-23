from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import UUID

from psycopg.types.json import Jsonb

from underwright.domain.quote_document import QuoteDocument
from underwright.infrastructure.postgres.quote_document_repository import (
    PostgresQuoteDocumentRepository,
)

REQUEST_ID = UUID("80000000-0000-0000-0000-000000000001")


class FakeCursor:
    def __init__(self, row: dict | None = None) -> None:
        self.row = row
        self.executed = None

    def execute(self, sql: str, params) -> None:
        self.executed = (sql, params)

    def fetchone(self):
        return self.row

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


class PostgresQuoteDocumentRepositoryTestCase(unittest.TestCase):
    def test_save_wraps_jsonb_and_commits(self) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        row = {
            "id": 55,
            "quote_request_id": REQUEST_ID,
            "template_id": 7,
            "generation_status": "success",
            "rendered_text": "Unsigned quote",
            "rendered_json": {"ok": True},
            "file_url": None,
            "created_at": now,
            "updated_at": now,
        }
        cursor = FakeCursor(row)
        connection = FakeConnection(cursor)
        repository = PostgresQuoteDocumentRepository(lambda: connection)
        document = QuoteDocument(
            quote_request_id=REQUEST_ID,
            template_id=7,
            generation_status="success",
            rendered_text="Unsigned quote",
            rendered_json={"ok": True},
            created_at=now,
            updated_at=now,
        )

        saved = repository.save(document)

        self.assertEqual(saved.id, 55)
        self.assertTrue(connection.committed)
        self.assertIsInstance(cursor.executed[1][4], Jsonb)


if __name__ == "__main__":
    unittest.main()
