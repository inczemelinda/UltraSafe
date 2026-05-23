from __future__ import annotations

import unittest
from uuid import UUID

from underwright.application.services.quote_request_service import QuoteRequestService
from underwright.domain.auth_user import AuthUser
from underwright.domain.quote_decision_audit import (
    QuoteDecisionAuditCreate,
    QuoteDecisionAuditRecord,
)
from underwright.domain.quote_request import QuoteRequest


REQUEST_ID = UUID("90000000-0000-0000-0000-000000000001")
CLIENT_ID = 1001


def priced_quote_request() -> QuoteRequest:
    return QuoteRequest(
        request_id=REQUEST_ID,
        client_id=CLIENT_ID,
        request_status="underwriter_review",
        client_data={
            "full_name": "Ion Popescu",
            "email": "ion@example.test",
            "phone": "+40700000000",
        },
        asset_data={
            "asset_type": "Apartment",
            "usage_type": "Owner occupied",
            "construction_type": "Concrete",
            "year_built": 1998,
            "area_sqm": 70,
            "declared_value": 300000,
            "occupancy": "Owner occupied",
            "previous_claims_count": 0,
        },
        pricing_preview={
            "request_details": {
                "coverage_amount": 300000,
                "security_features": ["Alarm", "Smoke detector", "Sprinklers"],
            },
            "pricing": {
                "source": "preview",
                "finalPremium": 9999,
            },
            "risk_assessment": {
                "source": "preview",
                "riskScore": 1,
            },
        },
    )


class FakeQuoteRequestRepository:
    def __init__(self) -> None:
        self.created_request = None
        self.updated_request = None
        self.client_id = None
        self.request_status = None
        self.updated_status = None
        self.created_audit: QuoteDecisionAuditCreate | None = None
        self.audit_records: list[QuoteDecisionAuditRecord] = []

    def create_request(self, request: QuoteRequest) -> QuoteRequest:
        self.created_request = request
        return request

    def update_request(self, request: QuoteRequest) -> QuoteRequest:
        self.updated_request = request
        return request

    def get_request_by_id(self, request_id: UUID) -> QuoteRequest:
        return QuoteRequest(
            request_id=request_id,
            client_id=CLIENT_ID,
            request_status="quote_ready",
        )

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[QuoteRequest]:
        self.client_id = client_id
        return [
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=client_id,
                request_status="draft",
            )
        ]

    def list_requests_by_status(self, request_status: str) -> list[QuoteRequest]:
        self.request_status = request_status
        return [
            QuoteRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status=request_status,
            )
        ]

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> QuoteRequest:
        self.updated_status = (request_id, request_status)
        return QuoteRequest(
            request_id=request_id,
            client_id=CLIENT_ID,
            request_status=request_status,
        )

    def create_decision_audit(
        self,
        record: QuoteDecisionAuditCreate,
    ) -> QuoteDecisionAuditRecord:
        self.created_audit = record
        saved = QuoteDecisionAuditRecord(id=1, **record.model_dump())
        self.audit_records.insert(0, saved)
        return saved

    def list_decision_audit(
        self,
        request_id: UUID,
    ) -> list[QuoteDecisionAuditRecord]:
        return [
            record
            for record in self.audit_records
            if record.quote_request_id == request_id
        ]


class QuoteRequestServiceTestCase(unittest.TestCase):
    def test_create_quote_request_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="draft",
        )

        result = service.create_quote_request(request)

        self.assertIs(result, request)
        self.assertIs(repository.created_request, request)
        self.assertEqual(repository.created_request.risk["source"], "backend")
        self.assertEqual(
            repository.created_request.pricing_preview["pricing_status"],
            "unavailable",
        )

    def test_create_quote_request_returns_authoritative_backend_pricing(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)
        request = priced_quote_request()

        result = service.create_quote_request(request)

        self.assertIs(result, request)
        self.assertEqual(repository.created_request.pricing["source"], "backend")
        self.assertEqual(repository.created_request.pricing["finalPremium"], 513)
        self.assertEqual(repository.created_request.risk["source"], "backend")
        self.assertEqual(
            repository.created_request.pricing_preview["ui_context"][
                "submitted_quote_estimate"
            ]["values"]["pricing"]["finalPremium"],
            9999,
        )
        self.assertFalse(repository.created_request.pricing_preview["binding"])

    def test_save_step_updates_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        request = QuoteRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="pricing_in_progress",
            quote_steps=[
                {"step": "client_data", "completed": True},
                {"step": "asset_data", "completed": True},
            ],
            pricing_preview={"currency": "RON", "estimated_premium": 1200},
        )

        result = service.save_step_updates(request)

        self.assertIs(result, request)
        self.assertIs(repository.updated_request, request)
        self.assertEqual(
            repository.updated_request.quote_steps[1]["step"],
            "asset_data",
        )
        self.assertEqual(repository.updated_request.risk["source"], "backend")

    def test_list_client_quote_requests_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        result = service.list_client_quote_requests(CLIENT_ID)

        self.assertEqual(repository.client_id, CLIENT_ID)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].client_id, CLIENT_ID)
        self.assertEqual(result[0].risk["source"], "backend")

    def test_list_underwriter_review_quote_requests_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        result = service.list_underwriter_review_quote_requests()

        self.assertEqual(repository.request_status, "underwriter_review")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].request_status, "underwriter_review")

    def test_get_quote_request_detail_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        result = service.get_quote_request_detail(REQUEST_ID)

        self.assertEqual(result.request_id, REQUEST_ID)
        self.assertEqual(result.request_status, "quote_ready")
        self.assertEqual(result.risk["source"], "backend")

    def test_update_request_status_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        result = service.update_request_status(REQUEST_ID, "quote_ready")

        self.assertEqual(result.request_status, "quote_ready")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "quote_ready"))

    def test_update_underwriter_decision_records_audit(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)
        user = AuthUser(
            id=2,
            email="underwriter@example.test",
            password_hash="hash",
            role="underwriter",
            full_name="Under Writer",
        )

        result = service.update_underwriter_decision(
            REQUEST_ID,
            "approved",
            reason=" Risk acceptable. ",
            user=user,
        )

        self.assertEqual(result.request_status, "approved")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "approved"))
        assert repository.created_audit is not None
        self.assertEqual(repository.created_audit.previous_status, "quote_ready")
        self.assertEqual(repository.created_audit.decision_status, "approved")
        self.assertEqual(repository.created_audit.reason, "Risk acceptable.")
        self.assertEqual(repository.created_audit.decided_by_auth_user_id, 2)
        self.assertEqual(
            repository.created_audit.decided_by_email, "underwriter@example.test"
        )

    def test_list_decision_audit_wraps_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)
        repository.audit_records = [
            QuoteDecisionAuditRecord(
                id=1,
                quote_request_id=REQUEST_ID,
                previous_status="underwriter_review",
                decision_status="approved",
                decided_by_name="Under Writer",
                decided_by_email="underwriter@example.test",
            )
        ]

        records = service.list_decision_audit(REQUEST_ID)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision_status, "approved")

    def test_status_transition_helpers_delegate_to_repository(self) -> None:
        repository = FakeQuoteRequestRepository()
        service = QuoteRequestService(repository)

        underwriter_review = service.mark_underwriter_review(REQUEST_ID)
        self.assertEqual(underwriter_review.request_status, "underwriter_review")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "underwriter_review"))

        approved = service.mark_approved(REQUEST_ID)
        self.assertEqual(approved.request_status, "approved")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "approved"))

        disapproved = service.mark_disapproved(REQUEST_ID)
        self.assertEqual(disapproved.request_status, "disapproved")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "disapproved"))

        failed = service.mark_failed(REQUEST_ID)
        self.assertEqual(failed.request_status, "failed")
        self.assertEqual(repository.updated_status, (REQUEST_ID, "failed"))


if __name__ == "__main__":
    unittest.main()
