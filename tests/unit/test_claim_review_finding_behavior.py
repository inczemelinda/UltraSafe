from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from underwright.application.modules.claim_classification_module import (
    ClaimClassificationModule,
)
from underwright.application.modules.claim_confidence_module import (
    ClaimConfidenceModule,
)
from underwright.application.modules.claim_review_screen_builder_module import (
    ClaimReviewScreenBuilderModule,
)
from underwright.application.modules.claim_summary_module import ClaimSummaryModule
from underwright.application.modules.claim_validation_module import (
    ClaimValidationModule,
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
from underwright.application.services.claim_review_query_service import (
    ClaimReviewQueryService,
)
from underwright.application.workflows.claim_workflow import ClaimWorkflow
from underwright.application.workflows.coverage_precheck_workflow import (
    CoveragePrecheckWorkflow,
)
from underwright.domain.claim_analysis import (
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
    PolicyWordingSection,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest


REQUEST_ID = UUID("8a000000-0000-0000-0000-000000000001")


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
        if not self.saved_contexts:
            raise ValueError("ClaimCaseContext not found")
        return self.saved_contexts[-1]


class FakeExtractedDocumentDataService:
    def __init__(self, bundle: ExtractedDocumentBundle) -> None:
        self.bundle = bundle
        self.calls: list[str] = []

    def get_extracted_documents(
        self,
        claim_request_id: str,
        additional_attachments: list[ClaimAttachmentMetadata] | None = None,
    ) -> ExtractedDocumentBundle:
        self.calls.append(claim_request_id)
        return self.bundle


class FakeCoverageAssessmentService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def assess_coverage(
        self,
        *,
        claim_type: str,
        incident_description: str,
        incident_date: str | None,
        wording_sections: list[PolicyWordingSection],
        policy_profile: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "claim_type": claim_type,
                "incident_description": incident_description,
                "incident_date": incident_date,
                "wording_sections": wording_sections,
                "policy_profile": policy_profile,
            }
        )
        return self.response


def test_fire_claim_with_covered_llm_result_and_no_official_report_requests_evidence() -> None:
    workflow, _, _, llm_service = make_claim_workflow(
        make_claim_request(claim_type="Fire", emergency_services=False),
        extracted_documents=matching_document_bundle(claim_type="Fire"),
        llm_response=coverage_response("potentially_covered"),
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "in_review"
    assert result.review_view is not None
    assert result.review_view.coverage_assessment is not None
    assert result.review_view.coverage_assessment["coverage_status"] == (
        "potentially_covered"
    )
    assert (
        result.case_context.generated_outputs.document_consistency is not None
    )
    assert result.case_context.generated_outputs.document_consistency.status == (
        "no_discrepancies"
    )
    assert not result.case_context.generated_outputs.document_consistency.discrepancies
    assert "official_fire_incident_confirmation" in requirement_types(result)
    assert result.review_view.suggested_next_action == "request_evidence"
    assert llm_service.calls[0]["claim_type"] == "Fire"


def test_fire_claim_with_official_report_does_not_request_fire_confirmation() -> None:
    workflow, _, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Fire", emergency_services=False),
        extracted_documents=matching_document_bundle(
            claim_type="Fire",
            extra_documents=[official_report_document()],
        ),
        llm_response=coverage_response("potentially_covered"),
    )

    result = workflow.run(REQUEST_ID)

    assert result.review_view is not None
    assert "official_fire_incident_confirmation" not in requirement_types(result)
    assert "official_incident_confirmation" not in requirement_types(result)
    assert result.review_view.suggested_next_action == "underwriter_review"


def test_policy_number_mismatch_is_high_severity_and_routes_to_manual_review() -> None:
    workflow, _, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Theft"),
        extracted_documents=matching_document_bundle(
            claim_type="Theft",
            policy_number="PAD-999",
        ),
        llm_response=coverage_response("potentially_covered"),
    )

    result = workflow.run(REQUEST_ID)

    consistency = result.case_context.generated_outputs.document_consistency
    assert consistency is not None
    policy_discrepancy = next(
        discrepancy
        for discrepancy in consistency.discrepancies
        if discrepancy.field == "policy_number"
    )
    assert policy_discrepancy.severity == "high"
    assert result.review_view is not None
    assert result.review_view.suggested_next_action == "manual_review"


def test_address_mismatch_is_high_severity_and_routes_to_manual_review() -> None:
    workflow, _, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Theft"),
        extracted_documents=matching_document_bundle(
            claim_type="Theft",
            property_address="Cluj-Napoca",
        ),
        llm_response=coverage_response("potentially_covered"),
    )

    result = workflow.run(REQUEST_ID)

    consistency = result.case_context.generated_outputs.document_consistency
    assert consistency is not None
    address_discrepancy = next(
        discrepancy
        for discrepancy in consistency.discrepancies
        if discrepancy.field == "property_address"
    )
    assert address_discrepancy.severity == "high"
    assert result.review_view is not None
    assert result.review_view.suggested_next_action == "manual_review"


def test_short_description_requires_details_without_auto_dismissal() -> None:
    workflow, claim_repository, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Other", description="Too short"),
        extracted_documents=matching_document_bundle(claim_type="Other"),
        llm_response=coverage_response("insufficient_information"),
    )

    result = workflow.run(REQUEST_ID)

    assert result.review_view is not None
    assert result.review_view.coverage_assessment is not None
    assert result.review_view.coverage_assessment["coverage_status"] == (
        "insufficient_information"
    )
    assert "additional_incident_details" in requirement_types(result)
    assert result.review_view.suggested_next_action == "request_evidence"
    assert result.status == "in_review"
    assert claim_repository.request.request_status == "in_review"


@pytest.mark.parametrize(
    ("mocked_status", "expected_route"),
    [
        ("unclear", "needs_underwriter_review"),
        ("not_covered", "coverage_review_required"),
    ],
)
def test_unknown_claim_type_routes_without_auto_dismissal(
    mocked_status: str,
    expected_route: str,
) -> None:
    workflow, claim_repository, _, _ = make_precheck_workflow(
        make_claim_request(claim_type="Meteor impact"),
        llm_response=coverage_response(mocked_status),
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == expected_route
    assert claim_repository.request.request_status == expected_route
    assert result.status not in {"accepted", "rejected", "dismissed", "completed"}


def test_exclusion_match_routes_to_coverage_review_without_decision_language() -> None:
    workflow, claim_repository, case_repository, _ = make_precheck_workflow(
        make_claim_request(
            claim_type="Water damage",
            description="Long-running leak caused gradual wear and tear.",
        ),
        llm_response=coverage_response(
            "excluded",
            possible_exclusions=["exclusions.common_uncovered_events"],
            rationale="The wording may exclude gradual wear and tear.",
        ),
    )

    result = workflow.run(REQUEST_ID)
    query_service = ClaimReviewQueryService(
        ClaimRequestService(claim_repository),
        CaseContextService(case_repository),
    )
    latest_review = query_service.get_latest_claim_review(REQUEST_ID)

    assert result.status == "coverage_review_required"
    assert claim_repository.request.request_status == "coverage_review_required"
    assert result.status not in {"accepted", "rejected", "dismissed", "completed"}
    assert latest_review.review_view["coverage_assessment"]["coverage_status"] == (
        "excluded"
    )
    rendered_payload = str(latest_review.review_view).lower()
    assert "accepted" not in rendered_payload
    assert "rejected" not in rendered_payload


def test_missing_extracted_document_bundle_marks_insufficient_data_without_crashing() -> None:
    workflow, _, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Theft"),
        extracted_documents=ExtractedDocumentBundle(source="test", documents=[]),
        llm_response=coverage_response("potentially_covered"),
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "in_review"
    assert result.review_view is not None
    assert result.review_view.document_consistency["status"] == (
        "insufficient_document_data"
    )


def test_malformed_llm_result_falls_back_without_crashing_workflow() -> None:
    workflow, _, _, _ = make_claim_workflow(
        make_claim_request(claim_type="Fire"),
        extracted_documents=matching_document_bundle(
            claim_type="Fire",
            extra_documents=[official_report_document()],
        ),
        llm_response={
            "coverage_status": "accepted",
            "matched_wording_sections": ["coverage.fire_damage"],
            "possible_exclusions": [],
            "rationale": "Bad decisioning language from a malformed response.",
            "confidence": "certain",
        },
    )

    result = workflow.run(REQUEST_ID)

    assert result.status == "in_review"
    assert result.review_view is not None
    assert result.review_view.coverage_assessment is not None
    assert result.review_view.coverage_assessment["coverage_status"] == "unclear"
    assert result.review_view.coverage_assessment["confidence"] == "low"
    rendered_payload = str(result.review_view.model_dump(mode="json")).lower()
    assert "suggested_next_action': 'accept" not in rendered_payload
    assert "suggested_next_action': 'reject" not in rendered_payload


def test_query_review_adds_attachment_summary_only_with_current_provenance() -> None:
    request = make_claim_request(claim_type="Fire")
    request = request.model_copy(
        update={
            "claim_data": {
                **request.claim_data,
                "attachment_extraction_summary": {
                    "claim_request_id": str(REQUEST_ID),
                    "attachment_keys": ["photos-from-incident.pdf"],
                    "attachment_count": 1,
                    "summary": (
                        "## Extracted fields / AI interpretation\n"
                        "* **Damage amount:** 12000 RON"
                    ),
                    "source": "global_summary",
                },
            }
        }
    )
    query_service = ClaimReviewQueryService(
        ClaimRequestService(FakeClaimRequestRepository(request)),
        CaseContextService(FakeCaseContextRepository()),
    )

    latest_review = query_service.get_latest_claim_review(REQUEST_ID)

    findings = latest_review.review_view.get("ai_review_findings")
    assert findings
    assert findings[0]["finding_type"] == "document_summary"
    assert findings[0]["description"] == (
        "Document interpretation:\n"
        "- Damage amount: 12000 RON"
    )


def test_query_review_ignores_stale_attachment_summary_provenance() -> None:
    request = make_claim_request(claim_type="Fire")
    request = request.model_copy(
        update={
            "claim_data": {
                **request.claim_data,
                "attachment_extraction_summary": {
                    "claim_request_id": str(REQUEST_ID),
                    "attachment_keys": ["other-attachment"],
                    "attachment_count": 1,
                    "summary": "This summary belongs to a different attachment set.",
                    "source": "global_summary",
                },
            }
        }
    )
    query_service = ClaimReviewQueryService(
        ClaimRequestService(FakeClaimRequestRepository(request)),
        CaseContextService(FakeCaseContextRepository()),
    )

    latest_review = query_service.get_latest_claim_review(REQUEST_ID)

    assert "ai_review_findings" not in latest_review.review_view


def test_query_review_cleans_legacy_generic_attachment_summary_checklist() -> None:
    query_service = ClaimReviewQueryService(
        ClaimRequestService(
            FakeClaimRequestRepository(make_claim_request(claim_type="Water damage"))
        ),
        CaseContextService(FakeCaseContextRepository()),
    )

    formatted = query_service._format_attachment_summary_text(
        "\n".join(
            [
                "Document summary",
                "Key parties: Not specified",
                "Dates: Not specified",
                "Amounts: Not specified",
                "Policy or claim references: Not specified",
                "Incident details: Indoor flooding in the living room area.",
                "Visible damages: Water affecting floor, furniture, and plants.",
                "Coverage facts: Not specified",
                "Missing or unclear information: Source of water ingress.",
            ]
        )
    )

    assert formatted == (
        "Evidence signals:\n"
        "- Incident evidence: Indoor flooding in the living room area.\n"
        "- Visible damage: Water affecting floor, furniture, and plants.\n"
        "- Needs review: Source of water ingress."
    )
    assert "Not specified" not in formatted
    assert "Key parties" not in formatted

    inline_formatted = query_service._format_attachment_summary_text(
        'Evidence signals: - The photo "flooded.png" shows significant water '
        "accumulation in the living room. - No visible signs of fire, smoke, "
        "soot, scorching, or burn damage are present. Out of place / needs "
        "review: - The claim reason is Fire, but the evidence primarily "
        "describes water/flood damage. Follow-up: - Clarification is needed "
        "on how the water damage relates to the fire incident reported."
    )

    assert inline_formatted == (
        "Evidence signals:\n"
        '- The photo "flooded.png" shows significant water accumulation in the living room.\n'
        "- No visible signs of fire, smoke, soot, scorching, or burn damage are present.\n"
        "Out of place / needs review:\n"
        "- The claim reason is Fire, but the evidence primarily describes water/flood damage.\n"
        "Follow-up:\n"
        "- Clarification is needed on how the water damage relates to the fire incident reported."
    )


def test_claim_detail_frontend_uses_claim_workspace_tabs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "frontend/src/pages/EmployeePages.tsx").read_text()
    detail_component = source.split("export function EmployeeClaimDetailPage()", 1)[
        1
    ].split("interface ClaimEvidenceScaffoldItem", 1)[0]
    decision_component = source.split("function ClaimDecisionTab", 1)[1].split(
        "function ClaimDecisionContextFact",
        1,
    )[0]
    evidence_preview_modal = source.split("function ClaimEvidencePreviewModal", 1)[
        1
    ].split("function ClientDocumentPreviewModal", 1)[0]

    assert '{ id: "details", label: "Details" }' in source
    assert '{ id: "evidence", label: "Evidence" }' in source
    assert '{ id: "communicate", label: "Communicate" }' in source
    assert '{ id: "decision", label: "Decision" }' in source
    assert "Claim information" not in source
    assert "Claim details" in source
    assert "Client details" in source
    assert "Property details" not in source
    assert "Incident details" not in source
    assert "Legal and identity documents" in source
    assert "Client document preview:" in source
    assert "Document interpretation" in source
    assert "ID document" in source
    assert "Bank confirmation" in source
    assert "Proof of ownership" in source
    assert "Damage photos" in source
    assert "Other claim supporting documents" in source
    assert "Classification mismatch: this file is tagged as both client legal/profile document and claim evidence." in source
    assert "Evidence details" in evidence_preview_modal
    assert "Upload status" not in evidence_preview_modal
    assert "Extraction provenance" not in evidence_preview_modal
    assert "No AI extraction available for this claim evidence yet." not in source
    assert "ClaimWorkspaceIntro" not in source
    assert "Client-submitted claim intake information, kept as scaffolding for the review workspace." not in source
    assert "Claim-specific evidence, required supporting documents, and inbound attachments for this claim." not in source
    assert "Document request status with the client. This is static scaffolding until communication lifecycle endpoints exist." not in source
    assert "buildClaimUploadedDocumentRows" not in source
    assert 'documentRow("id-document"' not in source
    assert "AI review pending. Extracted fields and interpretation will appear here." not in source
    assert "Evidence preview:" in source
    assert "Client communication" in source
    assert "Requests" in source
    assert "Replies" in source
    assert "Evidence request draft" in source
    assert "No document requests have been sent for this claim." in source
    assert "Underwriter decision" in source
    assert "Decision justification" in source
    assert "Reword with AI" in source
    assert "AI suggested wording" in source
    assert "sanitizeClaimDecisionAiSuggestion" in source
    assert "claimDecisionFallbackSuggestion" in source
    assert "inferDecisionFromJustification" in source
    assert "Approve claim" in source
    assert "Deny claim" in source
    assert "Request on-site inspection" in source
    assert "Decision readiness" in source
    assert "Blocking issues" not in decision_component
    assert "claimDecisionBlockingIssues" not in decision_component
    assert "Claim denial submitted." not in source
    assert "claimDecisionActionLabel" not in source
    assert "This claim already has a final decision." not in source
    assert "Reopening or changing decisions is not exposed by the current backend contract." not in source
    assert "AI suggestion could not be generated. Please try again or continue manually." in source
    assert "AI recommendation" not in source
    assert "playDecisionSelectSound" in source
    assert "playDecisionConfirmSound" in source
    assert "Crosshair" in source
    assert 'color="#dc2626"' in source
    assert "decision-crosshair-active" in source
    assert "Communication history" not in source
    assert "Claim Review Findings" not in detail_component
    assert "Evidence Request Lifecycle" not in detail_component
    assert "AI Claim Review Summary" not in detail_component
    assert "<ScoreBadge score={claim.score}" not in detail_component
    assert "Likely valid" not in source
    assert "Recommendation: accept" not in detail_component


def test_claim_detail_legal_documents_filter_excludes_evidence_photos() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "frontend/src/pages/EmployeePages.tsx").read_text()
    details_source = source.split("function ClaimDetailsTab", 1)[1].split(
        "function buildClientLegalDocuments", 1
    )[0]
    photo_guard_source = source.split(
        "function isClaimEvidencePhotoLikeClientDocument", 1
    )[1].split("function normalizedTextIncludesPhrase", 1)[0]

    assert "clientLegalDocuments.filter(isVisibleClientLegalDocument)" in details_source
    assert "isClaimEvidencePhotoLikeClientDocument(document, text, source)" in details_source
    assert '"damage photos"' in photo_guard_source
    assert '"incident photos"' in photo_guard_source
    assert '"property photos"' in photo_guard_source
    assert '"claim evidence"' in photo_guard_source
    assert '"supporting evidence"' in photo_guard_source
    assert '"image"' in photo_guard_source
    assert '"contract document"' in details_source
    assert '"insurance contract"' in details_source
    assert '"contract",' not in details_source


def make_claim_workflow(
    request: ClaimRequest,
    *,
    extracted_documents: ExtractedDocumentBundle,
    llm_response: dict[str, Any],
):
    claim_repository = FakeClaimRequestRepository(request)
    claim_request_service = ClaimRequestService(claim_repository)
    case_repository = FakeCaseContextRepository()
    extracted_service = FakeExtractedDocumentDataService(extracted_documents)
    llm_service = FakeCoverageAssessmentService(llm_response)
    workflow = ClaimWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(
            claim_request_service,
            extracted_document_data_service=extracted_service,
        ),
        validation_module=ClaimValidationModule(),
        classification_module=ClaimClassificationModule(),
        summary_module=ClaimSummaryModule(),
        confidence_module=ClaimConfidenceModule(),
        review_screen_builder_module=ClaimReviewScreenBuilderModule(),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_repository),
        coverage_assessment_module=CoverageAssessmentModule(
            coverage_assessment_service=llm_service
        ),
        document_consistency_module=DocumentConsistencyModule(),
        evidence_requirement_module=EvidenceRequirementModule(),
    )
    return workflow, claim_repository, case_repository, llm_service


def make_precheck_workflow(
    request: ClaimRequest,
    *,
    llm_response: dict[str, Any],
):
    claim_repository = FakeClaimRequestRepository(request)
    claim_request_service = ClaimRequestService(claim_repository)
    case_repository = FakeCaseContextRepository()
    llm_service = FakeCoverageAssessmentService(llm_response)
    workflow = CoveragePrecheckWorkflow(
        claim_request_service=claim_request_service,
        claim_data_service=ClaimDataService(claim_request_service),
        coverage_assessment_module=CoverageAssessmentModule(
            coverage_assessment_service=llm_service
        ),
        case_context_factory=CaseContextFactory(),
        case_context_service=CaseContextService(case_repository),
    )
    return workflow, claim_repository, case_repository, llm_service


def make_claim_request(
    *,
    claim_type: str,
    description: str | None = None,
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
            "description": description
            or f"{claim_type} damaged the insured property and interior rooms.",
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
                metadata={"label": "Property ownership document"},
            ),
            ClaimAttachmentMetadata(
                file_name="existing-policy-document.pdf",
                content_type="application/pdf",
                size_bytes=100,
                metadata={"label": "Policy document"},
            ),
        ],
    )


def matching_document_bundle(
    *,
    claim_type: str,
    policy_number: str = "PAD-001",
    property_address: str = "Bucharest",
    extra_documents: list[ExtractedClaimDocument] | None = None,
) -> ExtractedDocumentBundle:
    documents = [
        make_document(
            "existing-policy-document.pdf",
            "policy_document",
            {
                "policy_number": policy_number,
                "insured_address": property_address,
                "coverage_limit": 100000,
            },
        ),
        make_document(
            "property-ownership-document.pdf",
            "property_ownership",
            {
                "property_address": property_address,
                "owner_name": "Ion Popescu",
            },
        ),
        make_document(
            "land-registry-extract.pdf",
            "land_registry_extract",
            {"property_address": property_address},
        ),
        make_document(
            "id-document.pdf",
            "id_document",
            {"full_name": "Ion Popescu"},
        ),
        make_document(
            "photos-from-incident.pdf",
            "incident_photos",
            {"damage_type": f"{claim_type.lower()} damage"},
        ),
    ]
    return ExtractedDocumentBundle(
        source="test",
        documents=[*documents, *(extra_documents or [])],
    )


def official_report_document() -> ExtractedClaimDocument:
    return make_document(
        "fire-service-report.pdf",
        "fire_service_report",
        {
            "authority_verified": True,
            "incident_type": "fire",
            "reference_number": "FS-123",
        },
    )


def make_document(
    filename: str,
    document_type: str,
    extracted_fields: dict[str, Any],
) -> ExtractedClaimDocument:
    return ExtractedClaimDocument(
        document_id=f"doc:{filename}",
        filename=filename,
        document_type=document_type,
        extracted_fields=extracted_fields,
        extraction_confidence=0.9,
        source="test",
    )


def coverage_response(
    coverage_status: str,
    *,
    possible_exclusions: list[str] | None = None,
    rationale: str = "Mocked wording-fit assessment.",
) -> dict[str, Any]:
    matched_sections = (
        ["coverage.fire_damage"] if coverage_status == "potentially_covered" else []
    )
    return {
        "coverage_status": coverage_status,
        "matched_wording_sections": matched_sections,
        "possible_exclusions": possible_exclusions or [],
        "rationale": rationale,
        "confidence": "high" if coverage_status == "potentially_covered" else "low",
    }


def requirement_types(result) -> set[str]:
    assert result.review_view is not None
    return {
        requirement["requirement_type"]
        for requirement in result.review_view.required_evidence
    }
