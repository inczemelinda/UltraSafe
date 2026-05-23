from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.application.workflows.coverage_precheck_workflow import (
    CoveragePrecheckWorkflow,
)
from underwright.domain.claim_analysis import (
    CoverageAssessmentResult,
    PolicyWordingSection,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimRequest


REQUEST_ID = UUID("60000000-0000-0000-0000-000000000001")


class FakeClaimRequestRepository:
    def __init__(self, request: ClaimRequest) -> None:
        self.request = request

    def create_request(self, request: ClaimRequest) -> ClaimRequest:
        self.request = request
        return request

    def get_request_by_id(self, request_id: UUID) -> ClaimRequest:
        if request_id != self.request.request_id:
            raise ValueError("ClaimRequest not found")
        return self.request

    def list_requests_by_client_id(self, client_id):
        return [self.request] if self.request.client_id == client_id else []

    def list_requests_by_status(self, request_status: str):
        return [self.request] if self.request.request_status == request_status else []

    def update_request_status(
        self,
        request_id: UUID,
        request_status: str,
    ) -> ClaimRequest:
        if request_id != self.request.request_id:
            raise ValueError("ClaimRequest not found")
        self.request = self.request.model_copy(
            update={"request_status": request_status}
        )
        return self.request


class FakeCaseContextRepository:
    def __init__(self) -> None:
        self.saved_contexts: list[ClaimCaseContext] = []

    def save_case_context(self, context: ClaimCaseContext) -> ClaimCaseContext:
        self.saved_contexts.append(context)
        return context

    def get_case_context_by_case_id(self, case_id):
        return self.saved_contexts[-1]

    def get_latest_claim_case_context_by_request_id(self, request_id):
        return self.saved_contexts[-1]


class FakeCoverageAssessmentService:
    def __init__(self, coverage_status: str) -> None:
        self.coverage_status = coverage_status
        self.calls: list[dict[str, Any]] = []

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> CoverageAssessmentResult:
        self.calls.append(
            {
                "claim_type": claim_type,
                "incident_description": incident_description,
                "incident_date": incident_date,
                "wording_sections": wording_sections,
                "policy_profile": policy_profile,
            }
        )
        matched_sections = (
            [wording_sections[0].section_id]
            if self.coverage_status == "potentially_covered" and wording_sections
            else []
        )
        return CoverageAssessmentResult(
            coverage_status=self.coverage_status,
            matched_wording_sections=matched_sections,
            possible_exclusions=(
                ["exclusions.common_uncovered_events"]
                if self.coverage_status == "excluded"
                else []
            ),
            rationale="Mocked wording-fit assessment.",
            confidence="medium",
        )


class FailingCoverageAssessmentService:
    def assess_coverage(self, **kwargs):
        raise RuntimeError("LLM provider unavailable")


class FailingCoverageAssessmentModule:
    def evaluate(self, case_context: ClaimCaseContext):
        raise RuntimeError("precheck crashed")


def test_potentially_covered_screening_routes_to_underwriter_review() -> None:
    workflow, claim_repository, case_repository, assessment_service = make_workflow(
        make_request(),
        coverage_status="potentially_covered",
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "needs_underwriter_review"
    assert result.claim_request.request_status == "needs_underwriter_review"
    assert claim_repository.request.request_status == "needs_underwriter_review"
    assert result.coverage_assessment is not None
    assert result.coverage_assessment.coverage_status == "potentially_covered"
    assert result.coverage_assessment.assessed_at is not None
    assert len(case_repository.saved_contexts) == 1
    saved_context = case_repository.saved_contexts[0]
    assert saved_context.case_metadata.status == "needs_underwriter_review"
    assert saved_context.generated_outputs.coverage_assessment is not None
    loaded_context = case_repository.get_latest_claim_case_context_by_request_id(
        REQUEST_ID
    )
    assert loaded_context.generated_outputs.coverage_assessment is not None
    assert loaded_context.generated_outputs.coverage_assessment.coverage_status == (
        "potentially_covered"
    )
    assert "coverage.fire_damage" in (
        loaded_context.generated_outputs.coverage_assessment.wording_section_ids
    )
    assert saved_context.reference_data.extracted_documents.documents == []
    assert assessment_service.calls[0]["claim_type"] == "Fire"


@pytest.mark.parametrize(
    ("coverage_status", "expected_status"),
    [
        ("unclear", "needs_underwriter_review"),
        ("insufficient_information", "needs_underwriter_review"),
        ("not_covered", "coverage_review_required"),
        ("excluded", "coverage_review_required"),
    ],
)
def test_screening_routes_by_coverage_status(
    coverage_status: str,
    expected_status: str,
) -> None:
    workflow, _, case_repository, _ = make_workflow(
        make_request(),
        coverage_status=coverage_status,
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == expected_status
    assert result.claim_request.request_status == expected_status
    assert result.coverage_assessment is not None
    assert result.coverage_assessment.coverage_status == coverage_status
    assert case_repository.saved_contexts[0].case_metadata.status == expected_status


def test_llm_failure_falls_back_without_losing_claim() -> None:
    workflow, _, case_repository, _ = make_workflow(
        make_request(),
        coverage_assessment_service=FailingCoverageAssessmentService(),
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "needs_underwriter_review"
    assert result.claim_request.request_status == "needs_underwriter_review"
    assert result.coverage_assessment is not None
    assert result.coverage_assessment.coverage_status == "unclear"
    assert len(case_repository.saved_contexts) == 1


def test_precheck_crash_marks_claim_failed_without_losing_claim() -> None:
    workflow, claim_repository, case_repository, _ = make_workflow(
        make_request(),
        coverage_assessment_module=FailingCoverageAssessmentModule(),
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "failed"
    assert result.claim_request.request_status == "failed"
    assert claim_repository.request.request_status == "failed"
    assert result.case_context is not None
    assert result.case_context.checks_and_warnings.review_warnings == [
        "Initial coverage precheck failed; underwriter review is required."
    ]
    assert len(case_repository.saved_contexts) == 1


def make_workflow(
    request: ClaimRequest,
    *,
    coverage_status: str = "potentially_covered",
    coverage_assessment_service: object | None = None,
    coverage_assessment_module: object | None = None,
):
    claim_repository = FakeClaimRequestRepository(request)
    claim_request_service = ClaimRequestService(claim_repository)
    case_repository = FakeCaseContextRepository()
    assessment_service = coverage_assessment_service or FakeCoverageAssessmentService(
        coverage_status
    )
    module = coverage_assessment_module or CoverageAssessmentModule(
        coverage_assessment_service=assessment_service
    )
    workflow = CoveragePrecheckWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(claim_request_service),
        coverage_assessment_module=module,
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_repository),
    )
    return workflow, claim_repository, case_repository, assessment_service


def make_request() -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status="submitted",
        client_data={"full_name": "Ion Popescu"},
        claim_data={
            "claim_type": "Fire",
            "incident_date": "2026-05-01",
            "description": "Kitchen fire caused smoke and wall damage.",
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
        },
        attachments=[],
    )
