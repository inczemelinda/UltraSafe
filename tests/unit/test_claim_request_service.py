from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import UUID

from underwright.application.services.claim_request_service import (
    ClaimDecisionError,
    ClaimRequestService,
)
from underwright.domain.claim_request import ClaimRequest


REQUEST_ID = UUID("50000000-0000-0000-0000-000000000001")
CLIENT_ID = 1001


class FakeClaimRequestRepository:
    def __init__(self) -> None:
        self.requests: dict[UUID, ClaimRequest] = {}

    def create_request(self, request: ClaimRequest) -> ClaimRequest:
        self.requests[request.request_id] = request
        return request

    def get_request_by_id(self, request_id: UUID) -> ClaimRequest:
        try:
            return self.requests[request_id]
        except KeyError as exc:
            raise ValueError("ClaimRequest not found") from exc

    def list_requests_by_client_id(
        self,
        client_id: int | str | UUID,
    ) -> list[ClaimRequest]:
        return [
            request
            for request in self.requests.values()
            if request.client_id == client_id
        ]

    def list_requests_by_status(self, request_status: str) -> list[ClaimRequest]:
        return [
            request
            for request in self.requests.values()
            if request.request_status == request_status
        ]

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> ClaimRequest:
        request = self.get_request_by_id(request_id)
        updated_request = request.model_copy(
            update={"request_status": request_status}
        )
        self.requests[request_id] = updated_request
        return updated_request

    def update_request_attachments(
        self,
        request_id: UUID,
        attachments: list,
    ) -> ClaimRequest:
        request = self.get_request_by_id(request_id)
        updated_request = request.model_copy(update={"attachments": attachments})
        self.requests[request_id] = updated_request
        return updated_request

    def update_request_claim_data(
        self,
        request_id: UUID,
        claim_data: dict,
        request_status: str | None = None,
    ) -> ClaimRequest:
        request = self.get_request_by_id(request_id)
        update = {"claim_data": claim_data}
        if request_status is not None:
            update["request_status"] = request_status
        updated_request = request.model_copy(update=update)
        self.requests[request_id] = updated_request
        return updated_request

    def count_client_claims_since(self, client_id, since) -> int:
        return sum(
            1
            for request in self.requests.values()
            if request.client_id == client_id and request.created_at >= since
        )


class ClaimRequestServiceTestCase(unittest.TestCase):
    def test_create_client_claim_request(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="submitted",
            client_data={"full_name": "Ion Popescu"},
            claim_data={"claim_type": "property_damage"},
        )

        created_request = service.create_client_claim_request(request)

        self.assertEqual(created_request.request_id, REQUEST_ID)
        self.assertEqual(created_request.client_id, CLIENT_ID)
        self.assertEqual(created_request.request_status, "submitted")
        self.assertEqual(
            repository.requests[REQUEST_ID].client_data["full_name"],
            "Ion Popescu",
        )

    def test_list_client_claim_requests(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        request_1 = ClaimRequest(
            request_id=UUID("50000000-0000-0000-0000-000000000010"),
            client_id=CLIENT_ID,
            request_status="submitted",
        )
        request_2 = ClaimRequest(
            request_id=UUID("50000000-0000-0000-0000-000000000011"),
            client_id=CLIENT_ID,
            request_status="draft",
        )
        request_3 = ClaimRequest(
            request_id=UUID("50000000-0000-0000-0000-000000000012"),
            client_id=9999,
            request_status="submitted",
        )

        repository.create_request(request_1)
        repository.create_request(request_2)
        repository.create_request(request_3)

        requests = service.list_client_claim_requests(CLIENT_ID)

        self.assertEqual(len(requests), 2)
        self.assertTrue(
            all(request.client_id == CLIENT_ID for request in requests)
        )

    def test_list_underwriter_claim_queue_requests(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        submitted_request = ClaimRequest(
            request_id=UUID("50000000-0000-0000-0000-000000000020"),
            client_id=CLIENT_ID,
            request_status="submitted",
        )
        draft_request = ClaimRequest(
            request_id=UUID("50000000-0000-0000-0000-000000000021"),
            client_id=CLIENT_ID,
            request_status="draft",
        )

        repository.create_request(submitted_request)
        repository.create_request(draft_request)

        requests = service.list_underwriter_claim_queue_requests()

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].request_status, "submitted")

    def test_get_claim_request_detail(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=CLIENT_ID,
            request_status="submitted",
        )

        repository.create_request(request)

        result = service.get_claim_request_detail(REQUEST_ID)

        self.assertEqual(result.request_id, REQUEST_ID)
        self.assertEqual(result.client_id, CLIENT_ID)

    def test_mark_in_review(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="submitted",
            )
        )

        updated_request = service.mark_in_review(REQUEST_ID)

        self.assertEqual(updated_request.request_status, "in_review")

    def test_start_underwriter_review_moves_submitted_claim_to_in_review(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="submitted",
            )
        )

        updated_request = service.start_underwriter_review(REQUEST_ID)

        self.assertEqual(updated_request.request_status, "in_review")

    def test_start_underwriter_review_leaves_non_submitted_claim_unchanged(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="completed",
            )
        )

        updated_request = service.start_underwriter_review(REQUEST_ID)

        self.assertEqual(updated_request.request_status, "completed")

    def test_precheck_status_helpers(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="submitted",
            )
        )

        screening_request = service.mark_screening(REQUEST_ID)
        needs_review_request = service.mark_needs_underwriter_review(REQUEST_ID)
        coverage_review_request = service.mark_coverage_review_required(REQUEST_ID)

        self.assertEqual(screening_request.request_status, "screening")
        self.assertEqual(
            needs_review_request.request_status,
            "needs_underwriter_review",
        )
        self.assertEqual(
            coverage_review_request.request_status,
            "coverage_review_required",
        )

    def test_mark_completed(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="in_review",
            )
        )

        updated_request = service.mark_completed(REQUEST_ID)

        self.assertEqual(updated_request.request_status, "completed")

    def test_mark_failed(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)

        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="in_review",
            )
        )

        updated_request = service.mark_failed(REQUEST_ID)

        self.assertEqual(updated_request.request_status, "failed")

    def test_submit_claim_decision_persists_approved_decision(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)
        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="in_review",
            )
        )

        updated_request = service.submit_claim_decision(
            REQUEST_ID,
            decision="approved",
            justification="Covered loss with complete evidence.",
            decided_by_auth_user_id=22,
            decided_by_email="underwriter@example.test",
        )

        self.assertEqual(updated_request.request_status, "completed")
        self.assertEqual(updated_request.claim_data["decision"], "approved")
        self.assertEqual(updated_request.claim_data["decision_status"], "submitted")
        self.assertEqual(
            updated_request.claim_data["decision_justification"],
            "Covered loss with complete evidence.",
        )
        self.assertEqual(updated_request.claim_data["decided_by"], 22)
        self.assertEqual(
            updated_request.claim_data["decided_by_email"],
            "underwriter@example.test",
        )
        self.assertTrue(updated_request.claim_data["decided_at"])

    def test_submit_claim_decision_requires_justification(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)
        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="in_review",
            )
        )

        with self.assertRaises(ClaimDecisionError) as exc:
            service.submit_claim_decision(
                REQUEST_ID,
                decision="denied",
                justification=" ",
                decided_by_auth_user_id=22,
                decided_by_email="underwriter@example.test",
            )

        self.assertEqual(exc.exception.code, "CLAIM_DECISION_JUSTIFICATION_REQUIRED")

    def test_submit_claim_decision_persists_inspection_request(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)
        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="in_review",
            )
        )

        updated_request = service.submit_claim_decision(
            REQUEST_ID,
            decision="inspection_requested",
            justification="An on-site inspection is required before settlement.",
            decided_by_auth_user_id=22,
            decided_by_email="underwriter@example.test",
        )

        self.assertEqual(
            updated_request.request_status,
            "needs_underwriter_review",
        )
        self.assertEqual(
            updated_request.claim_data["decision"],
            "inspection_requested",
        )
        self.assertEqual(updated_request.claim_data["decision_status"], "submitted")

    def test_submit_claim_decision_blocks_duplicate_decision(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)
        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="completed",
                claim_data={
                    "decision": "approved",
                    "decision_status": "submitted",
                    "decision_justification": "Covered loss.",
                    "decided_at": "2026-05-15T10:00:00+00:00",
                },
            )
        )

        with self.assertRaises(ClaimDecisionError) as exc:
            service.submit_claim_decision(
                REQUEST_ID,
                decision="denied",
                justification="New decision.",
                decided_by_auth_user_id=22,
                decided_by_email="underwriter@example.test",
            )

        self.assertEqual(exc.exception.code, "CLAIM_DECISION_ALREADY_SUBMITTED")

    def test_mark_decision_email_sent_persists_email_metadata(self) -> None:
        repository = FakeClaimRequestRepository()
        service = ClaimRequestService(repository)
        repository.create_request(
            ClaimRequest(
                request_id=REQUEST_ID,
                client_id=CLIENT_ID,
                request_status="completed",
                claim_data={
                    "decision": "approved",
                    "decision_status": "submitted",
                    "decided_at": "2026-05-15T09:00:00+00:00",
                },
            )
        )

        updated_request = service.mark_decision_email_sent(
            REQUEST_ID,
            email_message_id=UUID("60000000-0000-0000-0000-000000000001"),
            sent_at=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(
            updated_request.claim_data["decision_email_message_id"],
            "60000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(
            updated_request.claim_data["decision_email_sent_at"],
            "2026-05-15T10:00:00+00:00",
        )
