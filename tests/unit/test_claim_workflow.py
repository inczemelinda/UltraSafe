from __future__ import annotations

from uuid import UUID

from underwright.application.modules.claim_classification_module import (
    ClaimClassificationModule,
)
from underwright.application.modules.claim_confidence_module import ClaimConfidenceModule
from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.claim_summary_module import ClaimSummaryModule
from underwright.application.modules.claim_validation_module import ClaimValidationModule
from underwright.application.services.case_context_service import (
    CaseContextFactory,
    CaseContextService,
)
from underwright.application.services.claim_data_service import ClaimDataService
from underwright.application.services.extracted_document_data_service import (
    DemoFilenameClaimDocumentExtractor,
    ExtractedDocumentDataService,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.application.workflows.claim_workflow import ClaimWorkflow
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest

REQUEST_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


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
        self.request.request_status = request_status
        return self.request


class FakeCaseContextRepository:
    def __init__(self) -> None:
        self.saved_contexts = []

    def save_case_context(self, context):
        self.saved_contexts.append(context)
        return context

    def get_case_context_by_case_id(self, case_id):
        return self.saved_contexts[-1]


def make_request(
    *,
    missing_description: bool = False,
    claim_type: str = "Storm",
    emergency_services: bool = True,
) -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status="submitted",
        client_data={
            "full_name": "Ion Popescu",
            "email": "ion@example.test",
            "phone": "+40700000000",
        },
        claim_data={
            "claim_type": claim_type,
            "incident_date": "2026-05-01",
            "incident_time": "10:30",
            "description": "" if missing_description else (
                f"{claim_type} damage to the roof with visible property impact."
            ),
            "estimated_damage": 12000,
            "coverage_amount": 100000,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "contact_phone": "+40700000000",
            "contact_email": "ion@example.test",
            "emergency_services": emergency_services,
        },
        attachments=[
            ClaimAttachmentMetadata(
                file_name="photos-from-incident.pdf",
                content_type="application/pdf",
                size_bytes=100,
                metadata={"label": "Photos from incident"},
            ),
            ClaimAttachmentMetadata(
                file_name="property-ownership-document.pdf",
                content_type="application/pdf",
                size_bytes=100,
                metadata={"label": "Documents"},
            ),
        ],
    )


def make_workflow(
    request: ClaimRequest,
    case_repository: FakeCaseContextRepository,
    *,
    demo_filename_extraction: bool = False,
):
    claim_repository = FakeClaimRequestRepository(request)
    request_service = ClaimRequestService(claim_repository)
    extracted_document_service = (
        ExtractedDocumentDataService(
            request_service,
            extractor=DemoFilenameClaimDocumentExtractor(),
        )
        if demo_filename_extraction
        else None
    )
    return ClaimWorkflow(
        claim_request_service=request_service,
        claim_data_service=ClaimDataService(
            request_service,
            extracted_document_data_service=extracted_document_service,
        ),
        validation_module=ClaimValidationModule(),
        classification_module=ClaimClassificationModule(),
        summary_module=ClaimSummaryModule(),
        confidence_module=ClaimConfidenceModule(),
        review_screen_builder_module=ClaimReviewScreenBuilderModule(),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_repository),
    ), claim_repository


def test_claim_workflow_builds_review_view_and_persists_context() -> None:
    case_repository = FakeCaseContextRepository()
    workflow, claim_repository = make_workflow(make_request(), case_repository)

    result = workflow.run(REQUEST_ID)

    assert result.status == "in_review"
    assert claim_repository.request.request_status == "in_review"
    assert result.review_view is not None
    assert [module.status for module in result.module_results] == ["success"] * 7
    assert result.review_view.coverage_assessment is not None
    assert result.review_view.coverage_assessment["coverage_status"] == (
        "potentially_covered"
    )
    assert "ClaimConfidenceModule" not in [
        module.module_name for module in result.module_results
    ]
    assert len(case_repository.saved_contexts) == 1
    assert case_repository.saved_contexts[0].case_metadata.status == "in_review"


def test_claim_workflow_marks_filename_only_documents_unavailable_by_default() -> None:
    case_repository = FakeCaseContextRepository()
    workflow, _ = make_workflow(make_request(), case_repository)

    result = workflow.run(REQUEST_ID)

    extracted_documents = result.case_context.reference_data.extracted_documents
    assert extracted_documents.source == "attachment_extraction_metadata"
    assert [document.document_type for document in extracted_documents.documents] == [
        "unknown",
    ]
    assert extracted_documents.documents[0].extracted_fields == {}
    assert extracted_documents.documents[0].extraction_provenance == "unavailable"
    assert extracted_documents.documents[0].filename == "photos-from-incident.pdf"
    assert result.review_view is not None
    assert result.review_view.extracted_documents["documents"][0][
        "extraction_provenance"
    ] == "unavailable"


def test_claim_workflow_can_use_explicit_demo_extracted_documents() -> None:
    case_repository = FakeCaseContextRepository()
    workflow, _ = make_workflow(
        make_request(),
        case_repository,
        demo_filename_extraction=True,
    )

    result = workflow.run(REQUEST_ID)

    extracted_documents = result.case_context.reference_data.extracted_documents
    assert extracted_documents.source == "demo_mock_filename_adapter"
    assert [document.document_type for document in extracted_documents.documents] == [
        "incident_photos",
    ]
    assert extracted_documents.documents[0].extraction_provenance == "demo_mock"
    assert extracted_documents.documents[0].extracted_fields["visible_damage"] is True
    assert extracted_documents.documents[0].filename == "photos-from-incident.pdf"


def test_fire_claim_without_official_proof_requests_evidence() -> None:
    case_repository = FakeCaseContextRepository()
    workflow, _ = make_workflow(
        make_request(claim_type="Fire", emergency_services=False),
        case_repository,
    )

    result = workflow.run(REQUEST_ID)

    assert result.review_view is not None
    assert result.review_view.suggested_next_action == "request_evidence"
    assert result.review_view.required_evidence[0]["requirement_type"] == (
        "official_fire_incident_confirmation"
    )
    assert (
        result.case_context.generated_outputs.claim_review.recommendation
        == "request_evidence"
    )
    assert result.case_context.generated_outputs.confidence is None


def test_claim_workflow_fails_fast_and_persists_failed_context() -> None:
    case_repository = FakeCaseContextRepository()
    workflow, claim_repository = make_workflow(
        make_request(missing_description=True),
        case_repository,
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "failed"
    assert claim_repository.request.request_status == "failed"
    assert [module.module_name for module in result.module_results] == [
        "ClaimValidationModule"
    ]
    assert len(case_repository.saved_contexts) == 1
    assert case_repository.saved_contexts[0].case_metadata.status == "failed"
