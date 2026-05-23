from __future__ import annotations

from uuid import UUID

from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_analysis import ReceivedClaimEvidence
from underwright.domain.claim_case_context import ClaimCaseContext


class ClaimEvidenceIngestionService:
    """Records additional evidence metadata without parsing email or documents."""

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        claim_data_service: ClaimDataService,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.claim_data_service = claim_data_service
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service

    def record_received_evidence(
        self,
        request_id: UUID,
        evidence: ReceivedClaimEvidence,
    ) -> ClaimCaseContext:
        claim_request = self.claim_request_service.get_claim_request_detail(
            request_id
        )
        case_context = self._latest_or_new_context(request_id, claim_request.client_id)
        self.claim_data_service.attach_claim_request(
            case_context,
            claim_request,
            include_extracted_documents=False,
        )
        case_context.reference_data.received_evidence.append(evidence)
        case_context.reference_data.external_reference_data.setdefault(
            "evidence_receipts",
            [],
        ).append(evidence.model_dump(mode="json"))
        if evidence.evidence_request_id is not None:
            case_context.reference_data.external_reference_data.setdefault(
                "evidence_request_events",
                [],
            ).append(
                {
                    "evidence_request_id": str(evidence.evidence_request_id),
                    "status": "evidence_received",
                    "received_at": evidence.received_at.isoformat(),
                }
            )
        self.case_context_service.save_case_context(case_context)
        return case_context

    def _latest_or_new_context(
        self,
        request_id: UUID,
        client_id: int | str | UUID,
    ) -> ClaimCaseContext:
        try:
            return (
                self.case_context_service.get_latest_claim_case_context_by_request_id(
                    request_id
                )
            )
        except ValueError:
            return self.case_context_factory.create_claim_case_context_from_request_id(
                request_id,
                client_id=client_id,
                status="evidence_received",
            )


__all__ = ["ClaimEvidenceIngestionService"]
