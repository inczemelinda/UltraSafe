from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from underwright.application.ports import ClaimRequestRepository
from underwright.domain.claim_request import ClaimRequest

ClaimDecision = Literal["approved", "denied", "inspection_requested"]
SUPPORTED_CLAIM_DECISIONS: set[str] = {
    "approved",
    "denied",
    "inspection_requested",
}
CLAIM_DECISION_REQUEST_STATUS: dict[str, str] = {
    "approved": "completed",
    "denied": "completed",
    "inspection_requested": "needs_underwriter_review",
}


class ClaimDecisionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ClaimRequestService:
    """Wraps claim request repository access for UI-facing claim flows."""

    def __init__(self, claim_request_repository: ClaimRequestRepository) -> None:
        self.claim_request_repository = claim_request_repository

    def create_client_claim_request(self, request: ClaimRequest) -> ClaimRequest:
        return self.claim_request_repository.create_request(request)

    def list_client_claim_requests(
        self,
        client_id: int | str | UUID,
    ) -> list[ClaimRequest]:
        return self.claim_request_repository.list_requests_by_client_id(client_id)

    def list_underwriter_claim_queue_requests(
        self,
        request_status: str = "submitted",
    ) -> list[ClaimRequest]:
        return self.claim_request_repository.list_requests_by_status(request_status)

    def get_claim_request_detail(self, request_id: UUID) -> ClaimRequest:
        return self.claim_request_repository.get_request_by_id(request_id)

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> ClaimRequest:
        return self.claim_request_repository.update_request_status(
            request_id,
            request_status,
        )

    def mark_screening(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "screening")

    def mark_needs_underwriter_review(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "needs_underwriter_review")

    def mark_coverage_review_required(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "coverage_review_required")

    def mark_in_review(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "in_review")

    def start_underwriter_review(self, request_id: UUID) -> ClaimRequest:
        claim = self.get_claim_request_detail(request_id)
        if claim.request_status != "submitted":
            return claim
        return self.mark_in_review(request_id)

    def mark_completed(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "completed")

    def mark_failed(self, request_id: UUID) -> ClaimRequest:
        return self.update_request_status(request_id, "failed")

    def update_request_attachments(
        self,
        request_id: UUID,
        attachments: list,
    ) -> ClaimRequest:
        return self.claim_request_repository.update_request_attachments(
            request_id,
            attachments,
        )

    def update_request_claim_data(
        self,
        request_id: UUID,
        claim_data: dict[str, Any],
        request_status: str | None = None,
    ) -> ClaimRequest:
        return self.claim_request_repository.update_request_claim_data(
            request_id,
            claim_data,
            request_status,
        )

    def count_client_claims_since(
        self,
        client_id: int | str | UUID,
        since: datetime,
    ) -> int:
        return self.claim_request_repository.count_client_claims_since(client_id, since)

    def submit_claim_decision(
        self,
        request_id: UUID,
        *,
        decision: str,
        justification: str,
        decided_by_auth_user_id: int | None,
        decided_by_email: str | None,
    ) -> ClaimRequest:
        normalized_decision = decision.strip().lower()
        trimmed_justification = justification.strip()
        if normalized_decision not in SUPPORTED_CLAIM_DECISIONS:
            raise ClaimDecisionError(
                "CLAIM_DECISION_INVALID",
                "Claim decision must be approved, denied, or inspection_requested.",
            )
        if not trimmed_justification:
            raise ClaimDecisionError(
                "CLAIM_DECISION_JUSTIFICATION_REQUIRED",
                "Decision justification is required.",
            )

        claim = self.get_claim_request_detail(request_id)
        claim_data = dict(claim.claim_data or {})
        if _has_persisted_decision(claim_data):
            raise ClaimDecisionError(
                "CLAIM_DECISION_ALREADY_SUBMITTED",
                "Claim already has a submitted decision.",
            )
        if str(claim.request_status) in {"draft", "failed"}:
            raise ClaimDecisionError(
                "CLAIM_DECISION_STATE_INVALID",
                "Claim is not in a state where a decision can be submitted.",
            )

        now = datetime.now(timezone.utc)
        claim_data.update(
            {
                "decision": normalized_decision,
                "decision_status": "submitted",
                "decision_justification": trimmed_justification,
                "decided_by": decided_by_auth_user_id,
                "decided_by_email": decided_by_email,
                "decided_at": now.isoformat(),
            }
        )
        return self.claim_request_repository.update_request_claim_data(
            request_id,
            claim_data,
            CLAIM_DECISION_REQUEST_STATUS[normalized_decision],
        )

    def mark_decision_email_sent(
        self,
        request_id: UUID,
        *,
        email_message_id: UUID,
        sent_at: datetime,
    ) -> ClaimRequest:
        claim = self.get_claim_request_detail(request_id)
        claim_data: dict[str, Any] = dict(claim.claim_data or {})
        claim_data.update(
            {
                "decision_email_message_id": str(email_message_id),
                "decision_email_sent_at": sent_at.isoformat(),
                "decision_email_decision": claim_data.get("decision"),
                "decision_email_decided_at": claim_data.get("decided_at"),
            }
        )
        return self.claim_request_repository.update_request_claim_data(
            request_id,
            claim_data,
            None,
        )


def _has_persisted_decision(claim_data: dict[str, Any]) -> bool:
    decision = str(claim_data.get("decision") or "").strip().lower()
    status = str(claim_data.get("decision_status") or "").strip().lower()
    decided_at = str(claim_data.get("decided_at") or "").strip()
    return (
        decision in SUPPORTED_CLAIM_DECISIONS
        and status not in {"", "pending"}
        and bool(decided_at)
    )


__all__ = [
    "ClaimDecisionError",
    "ClaimRequestService",
    "SUPPORTED_CLAIM_DECISIONS",
]
