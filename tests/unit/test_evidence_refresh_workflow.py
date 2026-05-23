from __future__ import annotations

from uuid import UUID

from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
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
from underwright.application.workflows.evidence_refresh_workflow import (
    EvidenceRefreshWorkflow,
)
from underwright.domain.claim_analysis import (
    ClaimClassificationOutput,
    ClaimSummaryOutput,
    ClaimValidationOutput,
    CoverageAssessmentResult,
    ReceivedClaimEvidence,
    ReceivedEvidenceAttachment,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimRequest
from underwright.domain.module_result import ModuleResult


REQUEST_ID = UUID("70000000-0000-0000-0000-000000000001")


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

    def update_request_status(self, request_id: UUID, request_status: str):
        self.request = self.request.model_copy(
            update={"request_status": request_status}
        )
        return self.request


class FakeCaseContextRepository:
    def __init__(self, context: ClaimCaseContext) -> None:
        self.context = context
        self.saved_contexts: list[ClaimCaseContext] = []

    def save_case_context(self, context: ClaimCaseContext) -> ClaimCaseContext:
        self.context = context
        self.saved_contexts.append(context)
        return context

    def get_case_context_by_case_id(self, case_id):
        return self.context

    def get_latest_claim_case_context_by_request_id(self, request_id):
        if request_id != REQUEST_ID:
            raise ValueError("ClaimCaseContext not found")
        return self.context


class CountingCoverageAssessmentModule:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, case_context: ClaimCaseContext) -> ModuleResult:
        self.calls += 1
        case_context.generated_outputs.coverage_assessment = CoverageAssessmentResult(
            coverage_status="unclear",
            matched_wording_sections=[],
            possible_exclusions=[],
            rationale="Coverage facts changed and were reassessed.",
            confidence="low",
        )
        return ModuleResult(
            module_name="CoverageAssessmentModule",
            status="success",
            summary="Coverage reassessed.",
        )


def test_evidence_refresh_preserves_coverage_but_rebuilds_evidence_requirements() -> None:
    coverage_module = CountingCoverageAssessmentModule()
    workflow, case_repository = make_workflow(coverage_module)
    original_coverage = case_repository.context.generated_outputs.coverage_assessment

    result = workflow.run(REQUEST_ID)

    assert result.status == "completed"
    assert result.coverage_assessment_reran is False
    assert coverage_module.calls == 0
    assert result.case_context.generated_outputs.coverage_assessment is original_coverage
    assert result.case_context.generated_outputs.evidence_requirements is not None
    required_evidence = (
        result.case_context.generated_outputs.evidence_requirements.required_evidence
    )
    assert len(required_evidence) == 1
    assert (
        required_evidence[0].requirement_type
        == "official_fire_incident_confirmation"
    )
    assert required_evidence[0].status == "missing"
    assert result.review_view is not None
    assert result.review_view.suggested_next_action == "request_evidence"
    assert (
        result.case_context.reference_data.received_evidence[-1].refresh_status
        == "completed"
    )


def test_evidence_refresh_reruns_coverage_when_coverage_facts_change() -> None:
    coverage_module = CountingCoverageAssessmentModule()
    workflow, case_repository = make_workflow(coverage_module)

    result = workflow.run(
        REQUEST_ID,
        claim_fact_updates={
            "description": "Updated incident description from the client.",
        },
    )

    assert result.status == "completed"
    assert result.coverage_assessment_reran is True
    assert coverage_module.calls == 1
    assert (
        result.case_context.generated_outputs.coverage_assessment.coverage_status
        == "unclear"
    )
    assert (
        case_repository.context.reference_data.claim_request["claim_data"][
            "description"
        ]
        == "Updated incident description from the client."
    )


def make_workflow(coverage_module: CountingCoverageAssessmentModule):
    request = make_claim_request()
    claim_repository = FakeClaimRequestRepository(request)
    request_service = ClaimRequestService(claim_repository)
    context = make_case_context(request)
    case_repository = FakeCaseContextRepository(context)
    workflow = EvidenceRefreshWorkflow(
        claim_request_service=request_service,
        claim_data_service=ClaimDataService(request_service),
        document_consistency_module=DocumentConsistencyModule(),
        evidence_requirement_module=EvidenceRequirementModule(),
        review_screen_builder_module=ClaimReviewScreenBuilderModule(),
        coverage_assessment_module=coverage_module,
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_repository),
    )
    return workflow, case_repository


def make_claim_request() -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status="in_review",
        client_data={"full_name": "Ion Popescu"},
        claim_data={
            "claim_type": "Fire",
            "description": "Kitchen fire caused smoke and wall damage.",
            "estimated_damage": 12000,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "emergency_services": False,
        },
        attachments=[],
    )


def make_case_context(request: ClaimRequest) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.case_metadata.status = "in_review"
    context.reference_data.claim_request = request.model_dump(mode="json")
    context.reference_data.received_evidence = [
        ReceivedClaimEvidence(
            evidence_request_id="evidence-request-1",
            sender_email="client@example.test",
            attachments=[
                ReceivedEvidenceAttachment(
                    filename="fire-service-report.pdf",
                    storage_key="s3://claims/fire-service-report.pdf",
                    content_type="application/pdf",
                )
            ],
        )
    ]
    context.generated_outputs.validation = ClaimValidationOutput(is_valid=True)
    context.generated_outputs.classification = ClaimClassificationOutput(
        claim_type="Fire",
        category="property_damage",
        severity="medium",
        rationale="Fire claim.",
    )
    context.generated_outputs.summary = ClaimSummaryOutput(
        summary="Kitchen fire with smoke damage.",
        key_facts={},
    )
    context.generated_outputs.coverage_assessment = CoverageAssessmentResult(
        coverage_status="potentially_covered",
        matched_wording_sections=["coverage.fire_damage"],
        possible_exclusions=[],
        rationale="Fire wording may apply.",
        confidence="high",
    )
    return context
