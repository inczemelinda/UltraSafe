from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from underwright.application.modules.claim_classification_module import (
    ClaimClassificationModule,
)
from underwright.application.modules.claim_confidence_module import ClaimConfidenceModule
from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.claim_summary_module import ClaimSummaryModule
from underwright.application.modules.claim_validation_module import ClaimValidationModule
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
from underwright.domain.claim_review_models import ClaimReviewView
from underwright.domain.module_result import ModuleResult


class ClaimWorkflowResult(BaseModel):
    case_context: ClaimCaseContext
    review_view: ClaimReviewView | None = None
    module_results: list[ModuleResult] = Field(default_factory=list)
    status: str = "started"


class ClaimWorkflow:
    """Orchestrates deterministic claim AI review."""

    def __init__(
        self,
        claim_request_service: ClaimRequestService,
        claim_data_service: ClaimDataService,
        validation_module: ClaimValidationModule,
        classification_module: ClaimClassificationModule,
        summary_module: ClaimSummaryModule,
        confidence_module: ClaimConfidenceModule,
        review_screen_builder_module: ClaimReviewScreenBuilderModule,
        case_context_factory: CaseContextFactory,
        case_context_service: CaseContextService,
        coverage_assessment_module: CoverageAssessmentModule | None = None,
        document_consistency_module: DocumentConsistencyModule | None = None,
        evidence_requirement_module: EvidenceRequirementModule | None = None,
    ) -> None:
        self.claim_request_service = claim_request_service
        self.claim_data_service = claim_data_service
        self.validation_module = validation_module
        self.classification_module = classification_module
        self.summary_module = summary_module
        self.coverage_assessment_module = (
            coverage_assessment_module or CoverageAssessmentModule()
        )
        self.document_consistency_module = (
            document_consistency_module or DocumentConsistencyModule()
        )
        self.evidence_requirement_module = (
            evidence_requirement_module or EvidenceRequirementModule()
        )
        self.confidence_module = confidence_module
        self.review_screen_builder_module = review_screen_builder_module
        self.case_context_factory = case_context_factory
        self.case_context_service = case_context_service

    def run(self, request_id: UUID) -> ClaimWorkflowResult:
        claim_request = self.claim_request_service.get_claim_request_detail(request_id)
        claim_request = self.claim_request_service.mark_in_review(request_id)
        case_context = (
            self.case_context_factory.create_claim_case_context_from_request_id(
                request_id,
                client_id=claim_request.client_id,
                status="in_review",
            )
        )
        module_results: list[ModuleResult] = []
        self.claim_data_service.attach_claim_request(
            case_context,
            claim_request,
            include_extracted_documents=False,
        )

        for step in [
            self.validation_module.evaluate,
            self.classification_module.evaluate,
            self.summary_module.evaluate,
        ]:
            result = step(case_context)
            module_results.append(result)
            if result.status == "failed":
                return self._failed_result(case_context, request_id, module_results)

        self.claim_data_service.attach_extracted_documents(case_context, request_id)

        for step in [
            self.coverage_assessment_module.evaluate,
            self.document_consistency_module.evaluate,
            self.evidence_requirement_module.evaluate,
        ]:
            result = step(case_context)
            module_results.append(result)
            if result.status == "failed":
                return self._failed_result(case_context, request_id, module_results)

        review_result = self.review_screen_builder_module.build(case_context)
        module_results.append(review_result)
        if review_result.status == "failed":
            return self._failed_result(case_context, request_id, module_results)

        case_context.case_metadata.status = "in_review"
        self.case_context_service.save_case_context(case_context)
        return ClaimWorkflowResult(
            case_context=case_context,
            review_view=case_context.review_state.claim_review_view,
            module_results=module_results,
            status="in_review",
        )

    def _failed_result(
        self,
        case_context: ClaimCaseContext,
        request_id: UUID,
        module_results: list[ModuleResult],
    ) -> ClaimWorkflowResult:
        case_context.case_metadata.status = "failed"
        self.claim_request_service.mark_failed(request_id)
        self.case_context_service.save_case_context(case_context)
        return ClaimWorkflowResult(
            case_context=case_context,
            review_view=case_context.review_state.claim_review_view,
            module_results=module_results,
            status="failed",
        )


__all__ = ["ClaimWorkflow", "ClaimWorkflowResult"]
