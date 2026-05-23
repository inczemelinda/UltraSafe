from __future__ import annotations

import unittest
from uuid import UUID

import os
import psycopg

from pathlib import Path
from underwright.domain.claim_request import (
    ClaimAttachmentMetadata,
    ClaimRequest,
)
from underwright.infrastructure.postgres.claim_request_repository import (
    PostgresClaimRequestRepository,
)

REQUEST_ID = UUID("4f000000-0000-0000-0000-000000000001")
CLIENT_LIST_REQUEST_ID_1 = UUID("4f000000-0000-0000-0000-000000000010")
CLIENT_LIST_REQUEST_ID_2 = UUID("4f000000-0000-0000-0000-000000000011")
STATUS_LIST_REQUEST_ID_1 = UUID("4f000000-0000-0000-0000-000000000020")
STATUS_LIST_REQUEST_ID_2 = UUID("4f000000-0000-0000-0000-000000000021")
STATUS_LIST_REQUEST_ID_3 = UUID("4f000000-0000-0000-0000-000000000022")
TEST_REQUEST_IDS = (
    REQUEST_ID,
    CLIENT_LIST_REQUEST_ID_1,
    CLIENT_LIST_REQUEST_ID_2,
    STATUS_LIST_REQUEST_ID_1,
    STATUS_LIST_REQUEST_ID_2,
    STATUS_LIST_REQUEST_ID_3,
)
TEST_CLIENT_ID = 9_400_001
OTHER_TEST_CLIENT_ID = 9_400_002


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
        f"DELETE FROM claim_request WHERE request_id IN ({placeholders})",
        TEST_REQUEST_IDS,
    )


class PostgresClaimRequestRepositoryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        migration_path = (
            Path(__file__).resolve().parents[2] / "sql" / "003_claim_requests.sql"
        )

        with connect_or_skip() as conn:
            with conn.cursor() as cur:
                cur.execute(migration_path.read_text())
                conn.commit()

    def setUp(self) -> None:
        with connect_or_skip() as conn:
            with conn.cursor() as cur:
                delete_test_requests(cur)
                conn.commit()

    def test_create_and_load_claim_request(self) -> None:
        repository = PostgresClaimRequestRepository(connection_factory)

        request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=TEST_CLIENT_ID,
            request_status="submitted",
            client_data={
                "full_name": "Ion Popescu",
                "email": "ion.popescu@example.test",
                "phone": "0712345678",
            },
            claim_data={
                "claim_type": "property_damage",
                "incident_date": "2026-05-10",
                "estimated_damage_ron": 25000,
                "description": "Water leak caused ceiling damage",
            },
            attachments=[
                ClaimAttachmentMetadata(
                    file_name="damage_photo.jpg",
                    content_type="image/jpeg",
                    size_bytes=2048,
                    file_url="s3://claims/damage_photo.jpg",
                    metadata={
                        "uploaded_by": "client",
                        "document_type": "photo",
                    },
                ),
                ClaimAttachmentMetadata(
                    file_name="invoice.pdf",
                    content_type="application/pdf",
                    size_bytes=4096,
                    file_url="s3://claims/invoice.pdf",
                    metadata={
                        "uploaded_by": "client",
                        "document_type": "invoice",
                    },
                ),
            ],
        )

        saved_request = repository.create_request(request)

        self.assertEqual(saved_request.request_id, REQUEST_ID)
        self.assertEqual(saved_request.request_status, "submitted")
        self.assertEqual(
            saved_request.client_data["full_name"],
            "Ion Popescu",
        )

        loaded_request = repository.get_request_by_id(REQUEST_ID)

        self.assertEqual(loaded_request.request_id, REQUEST_ID)
        self.assertEqual(loaded_request.client_id, TEST_CLIENT_ID)
        self.assertEqual(loaded_request.request_status, "submitted")

        self.assertEqual(
            loaded_request.client_data["email"],
            "ion.popescu@example.test",
        )

        self.assertEqual(
            loaded_request.claim_data["claim_type"],
            "property_damage",
        )

        self.assertEqual(
            loaded_request.claim_data["estimated_damage_ron"],
            25000,
        )

        self.assertEqual(len(loaded_request.attachments), 2)

        self.assertEqual(
            loaded_request.attachments[0].file_name,
            "damage_photo.jpg",
        )

        self.assertEqual(
            loaded_request.attachments[1].content_type,
            "application/pdf",
        )

        self.assertEqual(
            loaded_request.attachments[1].metadata["document_type"],
            "invoice",
        )

        self.assertIsNotNone(loaded_request.created_at)
        self.assertIsNotNone(loaded_request.updated_at)

    def test_get_request_by_id_raises_when_missing(self) -> None:
        repository = PostgresClaimRequestRepository(connection_factory)

        missing_request_id = UUID(
            "49999999-0000-0000-0000-000000000999"
        )

        with self.assertRaises(ValueError):
            repository.get_request_by_id(missing_request_id)

    def test_list_requests_by_client_id(self) -> None:
        repository = PostgresClaimRequestRepository(connection_factory)

        request_1 = ClaimRequest(
            request_id=CLIENT_LIST_REQUEST_ID_1,
            client_id=TEST_CLIENT_ID,
            request_status="submitted",
        )

        request_2 = ClaimRequest(
            request_id=CLIENT_LIST_REQUEST_ID_2,
            client_id=TEST_CLIENT_ID,
            request_status="draft",
        )

        repository.create_request(request_1)
        repository.create_request(request_2)

        requests = repository.list_requests_by_client_id(TEST_CLIENT_ID)

        self.assertEqual(
            {request.request_id for request in requests},
            {CLIENT_LIST_REQUEST_ID_1, CLIENT_LIST_REQUEST_ID_2},
        )
        self.assertTrue(
            all(request.client_id == TEST_CLIENT_ID for request in requests)
        )

    def test_list_requests_by_status(self) -> None:
        repository = PostgresClaimRequestRepository(connection_factory)

        request_1 = ClaimRequest(
            request_id=STATUS_LIST_REQUEST_ID_1,
            client_id=TEST_CLIENT_ID,
            request_status="submitted",
        )

        request_2 = ClaimRequest(
            request_id=STATUS_LIST_REQUEST_ID_2,
            client_id=OTHER_TEST_CLIENT_ID,
            request_status="submitted",
        )

        request_3 = ClaimRequest(
            request_id=STATUS_LIST_REQUEST_ID_3,
            client_id=OTHER_TEST_CLIENT_ID + 1,
            request_status="draft",
        )

        repository.create_request(request_1)
        repository.create_request(request_2)
        repository.create_request(request_3)

        requests = repository.list_requests_by_status("submitted")
        expected_request_ids = {STATUS_LIST_REQUEST_ID_1, STATUS_LIST_REQUEST_ID_2}
        matching_test_requests = [
            request for request in requests if request.request_id in expected_request_ids
        ]

        self.assertEqual(
            {request.request_id for request in matching_test_requests},
            expected_request_ids,
        )
        self.assertTrue(
            all(request.request_status == "submitted" for request in requests)
        )

    def test_update_request_status(self) -> None:
        repository = PostgresClaimRequestRepository(connection_factory)

        request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=TEST_CLIENT_ID,
            request_status="submitted",
        )

        repository.create_request(request)

        updated_request = repository.update_request_status(
            REQUEST_ID,
            "in_review",
        )

        self.assertEqual(
            updated_request.request_status,
            "in_review",
        )

        loaded_request = repository.get_request_by_id(REQUEST_ID)

        self.assertEqual(
            loaded_request.request_status,
            "in_review",
        )
