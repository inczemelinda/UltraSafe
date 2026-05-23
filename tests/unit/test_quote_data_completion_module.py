from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.modules.quote_data_completion_module import (
    QuoteDataCompletionModule,
)
from underwright.domain.quote_case_context import QuoteCaseContext
from underwright.domain.quote_request import QuoteRequest

REQUEST_ID = UUID("91000000-0000-0000-0000-000000000001")
CLIENT_ID = 1001


def complete_quote_request() -> QuoteRequest:
    return QuoteRequest(
        request_id=REQUEST_ID,
        client_id=CLIENT_ID,
        request_status="pricing_in_progress",
        client_data={
            "full_name": "Ion Popescu",
            "email": "ion.popescu@example.test",
            "phone": "+40712345678",
        },
        asset_data={
            "asset_type": "apartment",
            "usage_type": "residential",
            "construction_type": "concrete",
            "year_built": 1986,
            "area_sqm": 68,
            "declared_value": 350000,
            "occupancy": "owner_occupied",
        },
    )


class QuoteDataCompletionModuleTestCase(unittest.TestCase):
    def test_incomplete_quote_remains_pricing_in_progress(self) -> None:
        module = QuoteDataCompletionModule()
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="pricing_in_progress",
            client_data={
                "full_name": "Ion Popescu",
                "email": "",
            },
            asset_data={
                "asset_type": "apartment",
            },
        )
        context = QuoteCaseContext()

        result = module.evaluate(quote_request, context)

        self.assertEqual(result.status, "success")
        self.assertEqual(quote_request.request_status, "pricing_in_progress")
        self.assertFalse(quote_request.mandatory_data_status["is_complete"])
        self.assertIn(
            "client_data.phone",
            quote_request.mandatory_data_status["missing_fields"],
        )
        self.assertIn(
            "asset_data.year_built",
            quote_request.mandatory_data_status["missing_fields"],
        )
        self.assertEqual(
            context.checks_and_warnings.missing_required_fields,
            quote_request.mandatory_data_status["missing_fields"],
        )

    def test_incomplete_draft_quote_remains_draft(self) -> None:
        module = QuoteDataCompletionModule()
        quote_request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="draft",
        )
        context = QuoteCaseContext()

        module.evaluate(quote_request, context)

        self.assertEqual(quote_request.request_status, "draft")
        self.assertFalse(quote_request.mandatory_data_status["is_complete"])

    def test_complete_quote_can_become_quote_ready(self) -> None:
        module = QuoteDataCompletionModule()
        quote_request = complete_quote_request()
        context = QuoteCaseContext()

        result = module.evaluate(quote_request, context)

        self.assertEqual(result.status, "success")
        self.assertEqual(quote_request.request_status, "quote_ready")
        self.assertTrue(quote_request.mandatory_data_status["is_complete"])
        self.assertEqual(quote_request.mandatory_data_status["missing_fields"], [])
        self.assertEqual(context.case_metadata.status, "quote_ready")
        self.assertEqual(
            context.domain_payload.quote_evaluation["mandatory_data_status"],
            quote_request.mandatory_data_status,
        )

    def test_tracks_completed_and_missing_fields_by_step(self) -> None:
        module = QuoteDataCompletionModule()
        quote_request = complete_quote_request()
        quote_request.asset_data["declared_value"] = None
        context = QuoteCaseContext()

        module.evaluate(quote_request, context)

        status = quote_request.mandatory_data_status

        self.assertIn(
            "full_name",
            status["completed_fields_by_step"]["client_data"],
        )
        self.assertIn(
            "asset_data.declared_value",
            status["missing_fields_by_step"]["asset_data"],
        )
        self.assertFalse(status["is_complete"])