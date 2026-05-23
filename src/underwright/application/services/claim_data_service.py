from __future__ import annotations

from uuid import UUID

from underwright.application.services.extracted_document_data_service import (
    ExtractedDocumentDataService,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimRequest


class ClaimDataService:
    """Loads persisted claim intake data into ClaimCaseContext."""

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        extracted_document_data_service: ExtractedDocumentDataService | None = None,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.extracted_document_data_service = (
            extracted_document_data_service
            or ExtractedDocumentDataService(claim_request_service)
        )

    def attach_claim_request_data(
        self,
        context: ClaimCaseContext,
        request_id: UUID,
    ) -> ClaimCaseContext:
        claim_request = self.claim_request_service.get_claim_request_detail(request_id)
        return self.attach_claim_request(context, claim_request)

    def attach_claim_request(
        self,
        context: ClaimCaseContext,
        claim_request: ClaimRequest,
        *,
        include_extracted_documents: bool = True,
    ) -> ClaimCaseContext:
        claim_data = claim_request.claim_data
        context.source_inputs.request_id = claim_request.request_id
        context.source_inputs.client_id = claim_request.client_id
        context.source_inputs.claim_id = claim_data.get("claim_id")
        context.source_inputs.policy_id = claim_data.get("policy_number")

        context.reference_data.claim_request = claim_request.model_dump(mode="json")
        if include_extracted_documents:
            self.attach_extracted_documents(context, claim_request.request_id)
        context.reference_data.client_profile = claim_request.client_data
        context.reference_data.policy_profile = {
            "policy_number": claim_data.get("policy_number"),
            "contract_id": claim_data.get("contract_id"),
            "property_address": claim_data.get("property_address"),
            "coverage_amount": claim_data.get("coverage_amount"),
        }
        context.domain_payload.claim_intake_payload = {
            "request_id": str(claim_request.request_id),
            "client_id": claim_request.client_id,
            "request_status": claim_request.request_status,
            "client_data": claim_request.client_data,
            "claim_data": claim_data,
            "attachments": [
                attachment.model_dump(mode="json")
                for attachment in claim_request.attachments
            ],
        }
        context.domain_payload.ai_review_payload = {
            "claim_data": claim_data,
            "attachments": context.domain_payload.claim_intake_payload["attachments"],
        }
        return context

    def attach_extracted_documents(
        self,
        context: ClaimCaseContext,
        claim_request_id: UUID,
    ) -> ClaimCaseContext:
        context.reference_data.extracted_documents = (
            self.extracted_document_data_service.get_extracted_documents(
                str(claim_request_id)
            )
        )
        return context


__all__ = ["ClaimDataService"]
