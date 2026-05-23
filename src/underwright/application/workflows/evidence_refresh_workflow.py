from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.modules.document_consistency_module import (
    DocumentConsistencyModule,
)
from underwright.application.modules.evidence_requirement_module import (
    EvidenceRequirementModule,
)
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimAttachmentMetadata
from underwright.domain.claim_review_models import ClaimReviewView
from underwright.domain.module_result import ModuleResult


logger = logging.getLogger(__name__)


class EvidenceRefreshWorkflowResult(BaseModel):
    case_context: ClaimCaseContext
    review_view: ClaimReviewView | None = None
    module_results: list[ModuleResult] = Field(default_factory=list)
    status: str = "pending"
    refresh_pending_reason: str | None = None
    coverage_assessment_reran: bool = False


class EvidenceRefreshWorkflow:
    """Refreshes document/evidence findings after additional evidence arrives.

    Coverage assessment is about the incident description and policy wording,
    so this workflow reruns CoverageAssessmentModule only when incoming metadata
    explicitly changes coverage-relevant claim facts.
    """

    coverage_fact_fields = {
        "claim_type",
        "incident_type",
        "description",
        "incident_date",
    }

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        claim_data_service: ClaimDataService,
        document_consistency_module: DocumentConsistencyModule,
        evidence_requirement_module: EvidenceRequirementModule,
        review_screen_builder_module: ClaimReviewScreenBuilderModule,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
        coverage_assessment_module: CoverageAssessmentModule | None = None,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.claim_data_service = claim_data_service
        self.document_consistency_module = document_consistency_module
        self.evidence_requirement_module = evidence_requirement_module
        self.review_screen_builder_module = review_screen_builder_module
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service
        self.coverage_assessment_module = coverage_assessment_module

    def run(
        self,
        request_id: UUID,
        *,
        claim_fact_updates: dict[str, Any] | None = None,
    ) -> EvidenceRefreshWorkflowResult:
        claim_request = self.claim_request_service.get_claim_request_detail(
            request_id
        )
        case_context = self._latest_or_new_context(request_id, claim_request.client_id)
        module_results: list[ModuleResult] = []
        self.claim_data_service.attach_claim_request(
            case_context,
            claim_request,
            include_extracted_documents=False,
        )
        self._apply_claim_fact_updates(case_context, claim_fact_updates or {})

        coverage_assessment_reran = False
        if self._coverage_facts_changed(claim_fact_updates or {}):
            if self.coverage_assessment_module is not None:
                coverage_result = self.coverage_assessment_module.evaluate(
                    case_context
                )
                module_results.append(coverage_result)
                coverage_assessment_reran = coverage_result.status == "success"
            else:
                case_context.checks_and_warnings.review_warnings.append(
                    "Coverage facts changed, but coverage refresh is not configured."
                )

        case_context.reference_data.extracted_documents = (
            self.claim_data_service.extracted_document_data_service.get_extracted_documents(
                str(request_id),
                additional_attachments=self._received_evidence_attachments(
                    case_context
                ),
            )
        )

        for step in [
            self.document_consistency_module.evaluate,
            self.evidence_requirement_module.evaluate,
        ]:
            result = step(case_context)
            module_results.append(result)
            if result.status == "failed":
                return self._pending_result(
                    case_context,
                    module_results,
                    "Evidence refresh module failed.",
                    coverage_assessment_reran=coverage_assessment_reran,
                )

        review_result = self.review_screen_builder_module.build(case_context)
        module_results.append(review_result)
        if review_result.status == "failed":
            return self._pending_result(
                case_context,
                module_results,
                review_result.summary,
                coverage_assessment_reran=coverage_assessment_reran,
            )

        self._mark_latest_evidence_refresh_status(case_context, "completed")
        self.case_context_service.save_case_context(case_context)
        return EvidenceRefreshWorkflowResult(
            case_context=case_context,
            review_view=case_context.review_state.claim_review_view,
            module_results=module_results,
            status="completed",
            coverage_assessment_reran=coverage_assessment_reran,
        )

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

    def _pending_result(
        self,
        case_context: ClaimCaseContext,
        module_results: list[ModuleResult],
        reason: str,
        *,
        coverage_assessment_reran: bool,
    ) -> EvidenceRefreshWorkflowResult:
        logger.info(
            "Evidence refresh is pending for claim_request_id=%s: %s",
            case_context.source_inputs.request_id,
            reason,
        )
        self._mark_latest_evidence_refresh_status(case_context, "pending")
        case_context.checks_and_warnings.review_warnings.append(reason)
        self.case_context_service.save_case_context(case_context)
        return EvidenceRefreshWorkflowResult(
            case_context=case_context,
            review_view=case_context.review_state.claim_review_view,
            module_results=module_results,
            status="pending",
            refresh_pending_reason=reason,
            coverage_assessment_reran=coverage_assessment_reran,
        )

    def _received_evidence_attachments(
        self,
        case_context: ClaimCaseContext,
    ) -> list[ClaimAttachmentMetadata]:
        attachments: list[ClaimAttachmentMetadata] = []
        for evidence in case_context.reference_data.received_evidence:
            for attachment in evidence.attachments:
                attachments.append(
                    ClaimAttachmentMetadata(
                        file_name=attachment.filename,
                        content_type=attachment.content_type
                        or "application/octet-stream",
                        size_bytes=0,
                        file_url=attachment.storage_key,
                        metadata={
                            "source": evidence.source,
                            "sender_email": evidence.sender_email,
                            "received_at": evidence.received_at.isoformat(),
                            "refresh_status": evidence.refresh_status,
                            "evidence_request_id": (
                                str(evidence.evidence_request_id)
                                if evidence.evidence_request_id is not None
                                else None
                            ),
                            "document_id": (
                                str(attachment.document_id)
                                if attachment.document_id is not None
                                else None
                            ),
                            "storage_key": attachment.storage_key,
                        },
                    )
                )
        return attachments

    def _apply_claim_fact_updates(
        self,
        case_context: ClaimCaseContext,
        claim_fact_updates: dict[str, Any],
    ) -> None:
        if not claim_fact_updates:
            return
        claim_request = case_context.reference_data.claim_request
        claim_data = claim_request.setdefault("claim_data", {})
        claim_data.update(claim_fact_updates)
        case_context.domain_payload.claim_intake_payload.setdefault(
            "claim_data",
            {},
        ).update(claim_fact_updates)
        case_context.domain_payload.ai_review_payload.setdefault(
            "claim_data",
            {},
        ).update(claim_fact_updates)

    def _coverage_facts_changed(self, claim_fact_updates: dict[str, Any]) -> bool:
        return any(field in claim_fact_updates for field in self.coverage_fact_fields)

    def _mark_latest_evidence_refresh_status(
        self,
        case_context: ClaimCaseContext,
        status: str,
    ) -> None:
        if not case_context.reference_data.received_evidence:
            return
        latest_evidence = case_context.reference_data.received_evidence[-1]
        latest_evidence.refresh_status = status
        receipts = case_context.reference_data.external_reference_data.get(
            "evidence_receipts",
            [],
        )
        if isinstance(receipts, list) and receipts:
            receipts[-1]["refresh_status"] = status


__all__ = ["EvidenceRefreshWorkflow", "EvidenceRefreshWorkflowResult"]
