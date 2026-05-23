from __future__ import annotations

import os
import unittest
from pathlib import Path
from uuid import UUID

import psycopg

from underwright.domain.quote_decision_audit import QuoteDecisionAuditCreate
from underwright.domain.quote_request import (
    QuoteAttachmentMetadata,
    QuoteRequest,
)
from underwright.infrastructure.postgres.quote_request_repository import (
    PostgresQuoteRequestRepository,
)

REQUEST_ID = UUID("8f000000-0000-0000-0000-000000000001")
CLIENT_LIST_REQUEST_ID_1 = UUID("8f000000-0000-0000-0000-000000000010")
CLIENT_LIST_REQUEST_ID_2 = UUID("8f000000-0000-0000-0000-000000000011")
CLIENT_LIST_REQUEST_ID_3 = UUID("8f000000-0000-0000-0000-000000000012")
STATUS_LIST_REQUEST_ID_1 = UUID("8f000000-0000-0000-0000-000000000020")
STATUS_LIST_REQUEST_ID_2 = UUID("8f000000-0000-0000-0000-000000000021")
STATUS_LIST_REQUEST_ID_3 = UUID("8f000000-0000-0000-0000-000000000022")
TEST_REQUEST_IDS = (
    REQUEST_ID,
    CLIENT_LIST_REQUEST_ID_1,
    CLIENT_LIST_REQUEST_ID_2,
    CLIENT_LIST_REQUEST_ID_3,
    STATUS_LIST_REQUEST_ID_1,
    STATUS_LIST_REQUEST_ID_2,
    STATUS_LIST_REQUEST_ID_3,
)
TEST_CLIENT_ID = 9_800_001
OTHER_TEST_CLIENT_ID = 9_800_002


def connection_factory():
    return psycopg.connect(
        os.getenv(
            "DATABASE_URL",
            "postgresql://uw:uw@localhost:5432/uw_test",
        )
    )


def connect_or_skip():
    try:
        return connection_factory()
    except psycopg.OperationalError as exc:
        raise unittest.SkipTest(
            "Postgres test database is not reachable with DATABASE_URL. "
            f"Connection attempt failed: {exc}"
        ) from exc


def delete_test_requests(cur) -> None:
    placeholders = ", ".join(["%s"] * len(TEST_REQUEST_IDS))
    cur.execute(
        f"DELETE FROM quote_decision_audit WHERE quote_request_id IN ({placeholders})",
        TEST_REQUEST_IDS,
    )
    cur.execute(
        f"DELETE FROM quote_request WHERE request_id IN ({placeholders})",
        TEST_REQUEST_IDS,
    )


class PostgresQuoteRequestRepositoryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        migration_path = (
            Path(__file__).resolve().parents[2] / "sql" / "004_quote_requests.sql"
        )
        audit_migration_path = (
            Path(__file__).resolve().parents[2] / "sql" / "035_quote_decision_audit.sql"
        )

        with connect_or_skip() as conn:
            with conn.cursor() as cur:
                cur.execute(migration_path.read_text())
                cur.execute(audit_migration_path.read_text())
                conn.commit()

    def setUp(self) -> None:
        with connect_or_skip() as conn:
            with conn.cursor() as cur:
                delete_test_requests(cur)
                conn.commit()

    def test_create_and_load_quote_request(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=TEST_CLIENT_ID,
            request_status="pricing_in_progress",
            client_data={
                "full_name": "Ion Popescu",
                "email": "ion.popescu@example.test",
                "phone": "+40712345678",
            },
            asset_data={
                "asset_type": "apartment",
                "year_built": 1986,
                "area_sqm": 68,
            },
            quote_steps=[
                {"step": "client_data", "completed": True},
                {"step": "asset_data", "completed": True},
                {"step": "pricing", "completed": False},
            ],
            mandatory_data_status={
                "client_data": "complete",
                "asset_data": "complete",
                "attachments": "missing_optional",
            },
            attachments=[
                QuoteAttachmentMetadata(
                    file_name="property_photo.jpg",
                    content_type="image/jpeg",
                    size_bytes=2048,
                    file_url="s3://quotes/property_photo.jpg",
                    metadata={
                        "uploaded_by": "client",
                        "document_type": "photo",
                    },
                ),
                QuoteAttachmentMetadata(
                    file_name="ownership_document.pdf",
                    content_type="application/pdf",
                    size_bytes=4096,
                    file_url="s3://quotes/ownership_document.pdf",
                    metadata={
                        "uploaded_by": "client",
                        "document_type": "ownership_document",
                    },
                ),
            ],
            pricing_preview={
                "currency": "RON",
                "estimated_premium": 1490,
                "pricing_status": "preview",
            },
        )

        saved_request = repository.create_request(request)
        loaded_request = repository.get_request_by_id(REQUEST_ID)

        self.assertEqual(saved_request.request_id, REQUEST_ID)
        self.assertEqual(saved_request.request_status, "pricing_in_progress")

        self.assertEqual(loaded_request.request_id, REQUEST_ID)
        self.assertEqual(loaded_request.client_id, TEST_CLIENT_ID)
        self.assertEqual(loaded_request.request_status, "pricing_in_progress")

        self.assertEqual(
            loaded_request.client_data["email"],
            "ion.popescu@example.test",
        )
        self.assertEqual(
            loaded_request.asset_data["asset_type"],
            "apartment",
        )
        self.assertEqual(
            loaded_request.quote_steps[0]["step"],
            "client_data",
        )
        self.assertEqual(
            loaded_request.mandatory_data_status["attachments"],
            "missing_optional",
        )
        self.assertEqual(len(loaded_request.attachments), 2)
        self.assertEqual(
            loaded_request.attachments[0].file_name,
            "property_photo.jpg",
        )
        self.assertEqual(
            loaded_request.attachments[1].metadata["document_type"],
            "ownership_document",
        )
        self.assertEqual(
            loaded_request.pricing_preview["estimated_premium"],
            1490,
        )
        self.assertIsNotNone(loaded_request.created_at)
        self.assertIsNotNone(loaded_request.updated_at)

    def test_get_request_by_id_raises_when_missing(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        missing_request_id = UUID("89999999-0000-0000-0000-000000000999")

        with self.assertRaises(ValueError):
            repository.get_request_by_id(missing_request_id)

    def test_update_quote_request(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=TEST_CLIENT_ID,
            request_status="draft",
            client_data={"full_name": "Ion Popescu"},
            asset_data={"asset_type": "apartment"},
            quote_steps=[{"step": "client_data", "completed": True}],
            mandatory_data_status={"client_data": "complete"},
            pricing_preview={"currency": "RON", "estimated_premium": 1200},
        )

        repository.create_request(request)

        updated_request = request.model_copy(
            update={
                "request_status": "quote_ready",
                "asset_data": {
                    "asset_type": "apartment",
                    "area_sqm": 72,
                },
                "quote_steps": [
                    {"step": "client_data", "completed": True},
                    {"step": "asset_data", "completed": True},
                    {"step": "pricing", "completed": True},
                ],
                "mandatory_data_status": {
                    "client_data": "complete",
                    "asset_data": "complete",
                    "pricing": "complete",
                },
                "pricing_preview": {
                    "currency": "RON",
                    "estimated_premium": 1490,
                    "pricing_status": "ready",
                },
            }
        )

        saved_request = repository.update_request(updated_request)
        loaded_request = repository.get_request_by_id(REQUEST_ID)

        self.assertEqual(saved_request.request_status, "quote_ready")
        self.assertEqual(loaded_request.request_status, "quote_ready")
        self.assertEqual(loaded_request.asset_data["area_sqm"], 72)
        self.assertEqual(len(loaded_request.quote_steps), 3)
        self.assertEqual(
            loaded_request.mandatory_data_status["pricing"],
            "complete",
        )
        self.assertEqual(
            loaded_request.pricing_preview["estimated_premium"],
            1490,
        )

    def test_update_quote_request_raises_when_missing(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        missing_request = QuoteRequest(
            request_id=UUID("89999999-0000-0000-0000-000000000998"),
            client_id=TEST_CLIENT_ID,
            request_status="draft",
        )

        with self.assertRaises(ValueError):
            repository.update_request(missing_request)

    def test_list_requests_by_client_id(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        request_1 = QuoteRequest(
            request_id=CLIENT_LIST_REQUEST_ID_1,
            client_id=TEST_CLIENT_ID,
            request_status="draft",
        )
        request_2 = QuoteRequest(
            request_id=CLIENT_LIST_REQUEST_ID_2,
            client_id=TEST_CLIENT_ID,
            request_status="quote_ready",
        )
        request_3 = QuoteRequest(
            request_id=CLIENT_LIST_REQUEST_ID_3,
            client_id=OTHER_TEST_CLIENT_ID,
            request_status="draft",
        )

        repository.create_request(request_1)
        repository.create_request(request_2)
        repository.create_request(request_3)

        requests = repository.list_requests_by_client_id(TEST_CLIENT_ID)

        self.assertEqual(
            {request.request_id for request in requests},
            {CLIENT_LIST_REQUEST_ID_1, CLIENT_LIST_REQUEST_ID_2},
        )
        self.assertTrue(
            all(request.client_id == TEST_CLIENT_ID for request in requests)
        )

    def test_list_requests_by_status(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        request_1 = QuoteRequest(
            request_id=STATUS_LIST_REQUEST_ID_1,
            client_id=TEST_CLIENT_ID,
            request_status="underwriter_review",
        )
        request_2 = QuoteRequest(
            request_id=STATUS_LIST_REQUEST_ID_2,
            client_id=OTHER_TEST_CLIENT_ID,
            request_status="underwriter_review",
        )
        request_3 = QuoteRequest(
            request_id=STATUS_LIST_REQUEST_ID_3,
            client_id=OTHER_TEST_CLIENT_ID + 1,
            request_status="draft",
        )

        repository.create_request(request_1)
        repository.create_request(request_2)
        repository.create_request(request_3)

        requests = repository.list_requests_by_status("underwriter_review")
        expected_request_ids = {STATUS_LIST_REQUEST_ID_1, STATUS_LIST_REQUEST_ID_2}
        matching_test_requests = [
            request for request in requests if request.request_id in expected_request_ids
        ]

        self.assertEqual(
            {request.request_id for request in matching_test_requests},
            expected_request_ids,
        )
        self.assertTrue(
            all(
                request.request_status == "underwriter_review"
                for request in requests
            )
        )

    def test_update_quote_request_status(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=TEST_CLIENT_ID,
            request_status="pricing_in_progress",
        )

        repository.create_request(request)

        updated_request = repository.update_request_status(
            REQUEST_ID,
            "quote_ready",
        )

        self.assertEqual(updated_request.request_status, "quote_ready")

        loaded_request = repository.get_request_by_id(REQUEST_ID)

        self.assertEqual(loaded_request.request_status, "quote_ready")

    def test_update_quote_request_status_raises_when_missing(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)

        with self.assertRaises(ValueError):
            repository.update_request_status(
                UUID("89999999-0000-0000-0000-000000000997"),
                "failed",
            )

    def test_create_and_list_quote_decision_audit(self) -> None:
        repository = PostgresQuoteRequestRepository(connection_factory)
        repository.create_request(
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=TEST_CLIENT_ID,
                request_status="underwriter_review",
            )
        )

        first_record = repository.create_decision_audit(
            QuoteDecisionAuditCreate(
                quote_request_id=REQUEST_ID,
                previous_status="underwriter_review",
                decision_status="field_review_required",
                reason="Needs a roof inspection.",
                decided_by_auth_user_id=2,
                decided_by_name="Under Writer",
                decided_by_email="underwriter@example.test",
            )
        )
        second_record = repository.create_decision_audit(
            QuoteDecisionAuditCreate(
                quote_request_id=REQUEST_ID,
                previous_status="field_review_required",
                decision_status="approved",
                decided_by_auth_user_id=2,
                decided_by_name="Under Writer",
                decided_by_email="underwriter@example.test",
            )
        )

        records = repository.list_decision_audit(REQUEST_ID)

        self.assertEqual(records[0].id, second_record.id)
        self.assertEqual(records[1].id, first_record.id)
        self.assertEqual(records[1].reason, "Needs a roof inspection.")
        self.assertEqual(records[0].decided_by_email, "underwriter@example.test")
