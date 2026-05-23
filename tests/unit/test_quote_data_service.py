from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.services.quote_data_service import QuoteDataService
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_request import QuoteAttachmentMetadata, QuoteRequest


REQUEST_ID = UUID("92000000-0000-0000-0000-000000000001")
CLIENT_ID = 1001


class FakeQuoteRequestService:
    def __init__(self, quote_request: QuoteRequest | None = None) -> None:
        self.quote_request = quote_request
        self.request_id = None

    def get_quote_request_detail(self, request_id: UUID) -> QuoteRequest:
        self.request_id = request_id

        if self.quote_request is None:
            raise ValueError("QuoteRequest not found")

        return self.quote_request


class QuoteDataServiceTestCase(unittest.TestCase):
    def test_attach_quote_request_data_mutates_context(self) -> None:
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="pricing_in_progress",
            client_data={
                "full_name": "Ion Popescu",
                "email": "ion.popescu@example.test",
            },
            asset_data={
                "asset_type": "apartment",
                "area_sqm": 68,
            },
            quote_steps=[
                {"step": "client_data", "completed": True},
                {"step": "asset_data", "completed": True},
            ],
            mandatory_data_status={
                "is_complete": False,
                "missing_fields": ["asset_data.declared_value"],
            },
            attachments=[
                QuoteAttachmentMetadata(
                    file_name="property_photo.jpg",
                    content_type="image/jpeg",
                    size_bytes=2048,
                    file_url="s3://quotes/property_photo.jpg",
                    metadata={"uploaded_by": "client"},
                )
            ],
            pricing_preview={
                "currency": "RON",
                "estimated_premium": 1200,
            },
        )

        quote_request_service = FakeQuoteRequestService(quote_request)
        service = QuoteDataService(quote_request_service)
        context = QuoteCaseContext()

        result = service.attach_quote_request_data(context, REQUEST_ID)

        self.assertIs(result, context)
        self.assertEqual(quote_request_service.request_id, REQUEST_ID)

        self.assertEqual(context.source_inputs.request_id, REQUEST_ID)
        self.assertEqual(context.source_inputs.client_id, CLIENT_ID)

        self.assertEqual(
            context.reference_data.client_profile["email"],
            "ion.popescu@example.test",
        )
        self.assertEqual(
            context.reference_data.asset_profile["asset_type"],
            "apartment",
        )

        self.assertEqual(
            context.reference_data.quote_request["request_id"],
            str(REQUEST_ID),
        )

        self.assertEqual(
            context.domain_payload.quote_intake_payload["quote_steps"][0]["step"],
            "client_data",
        )
        self.assertEqual(
            context.domain_payload.quote_intake_payload["mandatory_data_status"][
                "missing_fields"
            ],
            ["asset_data.declared_value"],
        )
        self.assertEqual(
            context.domain_payload.quote_intake_payload["attachments"][0]["file_name"],
            "property_photo.jpg",
        )
        self.assertEqual(
            context.domain_payload.quote_evaluation["mandatory_data_status"][
                "is_complete"
            ],
            False,
        )
        self.assertEqual(
            context.generated_outputs.pricing_outputs.pricing_metadata[
                "estimated_premium"
            ],
            1200,
        )

    def test_missing_quote_request_fails_cleanly(self) -> None:
        service = QuoteDataService(FakeQuoteRequestService(None))
        context = QuoteCaseContext()

        with self.assertRaises(ValueError):
            service.attach_quote_request_data(context, REQUEST_ID)


if __name__ == "__main__":
    unittest.main()