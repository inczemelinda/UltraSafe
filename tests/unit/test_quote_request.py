from __future__ import annotations

import unittest
from uuid import UUID

from pydantic import ValidationError

from underwright.domain.quote_request import (
    QuoteAttachmentMetadata,
    QuoteRequest,
)

REQUEST_ID = UUID("60000000-0000-0000-0000-000000000001")
CLIENT_ID = UUID("70000000-0000-0000-0000-000000000001")


class QuoteRequestTestCase(unittest.TestCase):
    def test_quote_request_defaults_to_draft_status(self) -> None:
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
        )

        self.assertEqual(quote_request.request_status, "draft")
        self.assertEqual(quote_request.client_data, {})
        self.assertEqual(quote_request.asset_data, {})
        self.assertEqual(quote_request.quote_steps, [])
        self.assertEqual(quote_request.mandatory_data_status, {})
        self.assertEqual(quote_request.attachments, [])
        self.assertEqual(quote_request.pricing_preview, {})

    def test_quote_request_accepts_valid_statuses(self) -> None:
        valid_statuses = [
            "draft",
            "pricing_in_progress",
            "quote_ready",
            "auto_accepted",
            "underwriter_review",
            "approved",
            "disapproved",
            "field_review_required",
            "failed",
        ]

        for status in valid_statuses:
            with self.subTest(status=status):
                quote_request = QuoteRequest(
                    request_id=REQUEST_ID,
                    client_id=CLIENT_ID,
                    request_status=status,
                )

                self.assertEqual(quote_request.request_status, status)

    def test_quote_request_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="submitted",
            )

    def test_quote_request_contains_intake_sections(self) -> None:
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            client_data={"full_name": "Ion Popescu"},
            asset_data={"asset_type": "apartment"},
            quote_steps=[{"step": "asset_details", "completed": True}],
            mandatory_data_status={"client_data": "complete"},
            pricing_preview={"currency": "RON", "estimated_premium": 1200},
        )

        self.assertEqual(quote_request.client_data["full_name"], "Ion Popescu")
        self.assertEqual(quote_request.asset_data["asset_type"], "apartment")
        self.assertEqual(quote_request.quote_steps[0]["step"], "asset_details")
        self.assertEqual(
            quote_request.mandatory_data_status["client_data"],
            "complete",
        )
        self.assertEqual(quote_request.pricing_preview["currency"], "RON")

    def test_quote_request_exposes_only_backend_risk(self) -> None:
        preview_quote = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            pricing_preview={
                "risk_assessment": {
                    "source": "preview",
                    "riskScore": 40,
                }
            },
        )
        backend_quote = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            pricing_preview={
                "risk_assessment": {
                    "source": "backend",
                    "score": 70,
                    "level": "High",
                }
            },
        )

        self.assertIsNone(preview_quote.risk)
        self.assertEqual(backend_quote.risk["score"], 70)

    def test_quote_request_exposes_only_backend_pricing(self) -> None:
        preview_quote = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            pricing_preview={
                "pricing": {
                    "source": "preview",
                    "finalPremium": 9999,
                }
            },
        )
        backend_quote = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            pricing_preview={
                "pricing": {
                    "source": "backend",
                    "finalPremium": 513,
                }
            },
        )

        self.assertIsNone(preview_quote.pricing)
        self.assertEqual(backend_quote.pricing["finalPremium"], 513)

    def test_quote_request_contains_attachment_metadata(self) -> None:
        attachment = QuoteAttachmentMetadata(
            file_name="property_photo.jpg",
            content_type="image/jpeg",
            size_bytes=2048,
            file_url="s3://quotes/property_photo.jpg",
            metadata={"uploaded_by": "client"},
        )

        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            attachments=[attachment],
        )

        self.assertEqual(
            quote_request.attachments[0].file_name,
            "property_photo.jpg",
        )
        self.assertEqual(
            quote_request.attachments[0].metadata["uploaded_by"],
            "client",
        )

    def test_quote_request_does_not_embed_case_context(self) -> None:
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
        )

        self.assertFalse(hasattr(quote_request, "case_metadata"))
        self.assertFalse(hasattr(quote_request, "domain_payload"))
        self.assertFalse(hasattr(quote_request, "audit_trail"))

    def test_quote_request_sets_created_and_updated_timestamps(self) -> None:
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
        )

        self.assertIsNotNone(quote_request.created_at)
        self.assertIsNotNone(quote_request.updated_at)
