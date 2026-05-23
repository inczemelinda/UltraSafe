from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import UUID

from pydantic import ValidationError

from underwright.domain.claim_request import (
    build_claim_display_id,
    ClaimAttachmentMetadata,
    ClaimRequest,
)

REQUEST_ID = UUID("20000000-0000-0000-0000-000000000001")
CLIENT_ID = UUID("30000000-0000-0000-0000-000000000001")


class ClaimRequestTestCase(unittest.TestCase):
    def test_claim_request_defaults_to_draft_status(self) -> None:
        claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
        )

        self.assertEqual(claim_request.request_status, "draft")
        self.assertEqual(claim_request.client_data, {})
        self.assertEqual(claim_request.claim_data, {})
        self.assertEqual(claim_request.attachments, [])

    def test_claim_request_accepts_valid_statuses(self) -> None:
        valid_statuses = [
            "draft",
            "submitted",
            "screening",
            "needs_underwriter_review",
            "coverage_review_required",
            "in_review",
            "completed",
            "failed",
        ]

        for status in valid_statuses:
            with self.subTest(status=status):
                claim_request = ClaimRequest(
                    request_id=REQUEST_ID,
                    client_id=CLIENT_ID,
                    request_status=status,
                )

                self.assertEqual(claim_request.request_status, status)

    def test_claim_request_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="created",
            )

    def test_claim_request_keeps_claim_intake_data_separate(self) -> None:
        claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="submitted",
            client_data={"full_name": "Ion Popescu"},
            claim_data={"claim_type": "property_damage"},
        )

        self.assertEqual(claim_request.client_data["full_name"], "Ion Popescu")
        self.assertEqual(claim_request.claim_data["claim_type"], "property_damage")
        self.assertFalse(hasattr(claim_request, "case_metadata"))
        self.assertFalse(hasattr(claim_request, "domain_payload"))

    def test_claim_request_contains_attachment_metadata(self) -> None:
        attachment = ClaimAttachmentMetadata(
            file_name="damage_photo.jpg",
            content_type="image/jpeg",
            size_bytes=2048,
            file_url="s3://claims/damage_photo.jpg",
            metadata={"uploaded_by": "client"},
        )

        claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            attachments=[attachment],
        )

        self.assertEqual(
            claim_request.attachments[0].file_name,
            "damage_photo.jpg",
        )
        self.assertEqual(
            claim_request.attachments[0].metadata["uploaded_by"],
            "client",
        )

    def test_claim_request_sets_created_and_updated_timestamps(self) -> None:
        claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
        )

        self.assertIsNotNone(claim_request.created_at)
        self.assertIsNotNone(claim_request.updated_at)

    def test_claim_request_populates_human_display_claim_id(self) -> None:
        claim_request = ClaimRequest(
            request_id=UUID("22222222-2222-4222-8222-000000000009"),
            client_id=CLIENT_ID,
            created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
            claim_data={
                "claim_id": "22222222-2222-4222-8222-000000000009",
            },
        )

        self.assertEqual(
            claim_request.claim_data["display_claim_id"],
            "CLM-2026-000009",
        )
        self.assertEqual(
            claim_request.claim_data["claim_id"],
            "22222222-2222-4222-8222-000000000009",
        )

    def test_claim_request_preserves_non_uuid_claim_id_as_display_claim_id(self) -> None:
        claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
            claim_data={"claim_id": "CL-2026-001"},
        )

        self.assertEqual(
            claim_request.claim_data["display_claim_id"],
            "CL-2026-001",
        )

    def test_build_claim_display_id_uses_claim_uuid_suffix_without_exposing_uuid(self) -> None:
        self.assertEqual(
            build_claim_display_id(
                request_id=REQUEST_ID,
                created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
                claim_id="22222222-2222-4222-8222-000000000009",
            ),
            "CLM-2026-000009",
        )
