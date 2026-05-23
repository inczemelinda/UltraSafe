from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.domain.claim_analysis import CoverageAssessmentResult
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimRequest
from underwright.domain.module_result import ModuleResult


logger = logging.getLogger(__name__)


class CoveragePrecheckWorkflowResult(BaseModel):
    claim_request: ClaimRequest
    case_context: ClaimCaseContext | None = None
    coverage_assessment: CoverageAssessmentResult | None = None
    module_results: list[ModuleResult] = Field(default_factory=list)
    status: str


class CoveragePrecheckWorkflow:
    """Runs initial wording-based coverage screening after claim submission.

    `coverage_review_required` is a routing state for human coverage review.
    It is not dismissal, denial, rejection, or any other final claim decision.
    """

    REVIEW_STATUSES = {
        "potentially_covered": "needs_underwriter_review",
        "unclear": "needs_underwriter_review",
        "insufficient_information": "needs_underwriter_review",
        "not_covered": "coverage_review_required",
        "excluded": "coverage_review_required",
    }

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        claim_data_service: ClaimDataService,
        coverage_assessment_module: CoverageAssessmentModule,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.claim_data_service = claim_data_service
        self.coverage_assessment_module = coverage_assessment_module
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service

    def run(self, request_id: UUID) -> CoveragePrecheckWorkflowResult:
        claim_request = self.claim_request_service.get_claim_request_detail(
            request_id
        )
        case_context: ClaimCaseContext | None = None
        module_results: list[ModuleResult] = []

        try:
            claim_request = self.claim_request_service.mark_screening(request_id)
            case_context = (
                self.case_context_factory.create_claim_case_context_from_request_id(
                    request_id,
                    client_id=claim_request.client_id,
                    status="screening",
                )
            )
            self.claim_data_service.attach_claim_request(
                case_context,
                claim_request,
                include_extracted_documents=False,
            )

            module_result = self.coverage_assessment_module.evaluate(case_context)
            module_results.append(module_result)
            if module_result.status == "failed":
                raise RuntimeError(module_result.summary)

            coverage_assessment = case_context.generated_outputs.coverage_assessment
            routed_status = self._status_for(coverage_assessment)
            claim_request = self.claim_request_service.update_request_status(
                request_id,
                routed_status,
            )
            self._sync_claim_request_status(case_context, claim_request)
            case_context.case_metadata.status = routed_status
            self.case_context_service.save_case_context(case_context)
            return CoveragePrecheckWorkflowResult(
                claim_request=claim_request,
                case_context=case_context,
                coverage_assessment=coverage_assessment,
                module_results=module_results,
                status=routed_status,
            )
        except Exception:
            logger.exception(
                "Coverage precheck failed for claim_request_id=%s",
                request_id,
            )
            claim_request = self._mark_failed_safely(request_id, claim_request)
            if case_context is not None:
                case_context.case_metadata.status = claim_request.request_status
                case_context.checks_and_warnings.review_warnings.append(
                    "Initial coverage precheck failed; underwriter review is required."
                )
                self._sync_claim_request_status(case_context, claim_request)
                self._save_context_safely(case_context)
            return CoveragePrecheckWorkflowResult(
                claim_request=claim_request,
                case_context=case_context,
                coverage_assessment=(
                    case_context.generated_outputs.coverage_assessment
                    if case_context is not None
                    else None
                ),
                module_results=module_results,
                status=claim_request.request_status,
            )

    def _status_for(
        self,
        coverage_assessment: CoverageAssessmentResult | None,
    ) -> str:
        if coverage_assessment is None:
            return "needs_underwriter_review"
        return self.REVIEW_STATUSES.get(
            coverage_assessment.coverage_status,
            "needs_underwriter_review",
        )

    def _mark_failed_safely(
        self,
        request_id: UUID,
        fallback_claim_request: ClaimRequest,
    ) -> ClaimRequest:
        try:
            return self.claim_request_service.mark_failed(request_id)
        except Exception:
            logger.exception(
                "Failed to mark claim coverage precheck as failed for "
                "claim_request_id=%s",
                request_id,
            )
            return fallback_claim_request

    def _save_context_safely(self, case_context: ClaimCaseContext) -> None:
        try:
            self.case_context_service.save_case_context(case_context)
        except Exception:
            logger.exception(
                "Failed to persist failed coverage precheck context for "
                "claim_request_id=%s",
                case_context.source_inputs.request_id,
            )

    def _sync_claim_request_status(
        self,
        case_context: ClaimCaseContext,
        claim_request: ClaimRequest,
    ) -> None:
        case_context.reference_data.claim_request["request_status"] = (
            claim_request.request_status
        )
        case_context.domain_payload.claim_intake_payload["request_status"] = (
            claim_request.request_status
        )


__all__ = [
    "CoveragePrecheckWorkflow",
    "CoveragePrecheckWorkflowResult",
]
