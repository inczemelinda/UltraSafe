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
from underwright.application.modules.coverage_assessment_module import (
    CoverageAssessmentModule,
)
from underwright.application.modules.document_consistency_module import (
    DocumentConsistencyModule,
)
from underwright.application.modules.evidence_requirement_module import (
    EvidenceRequirementModule,
)
from underwright.domain.claim_analysis import (
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
)
from underwright.domain.claim_case_context import ClaimCaseContext

REQUEST_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def make_context(*, missing_description: bool = False) -> ClaimCaseContext:
    context = ClaimCaseContext()
    context.source_inputs.request_id = REQUEST_ID
    context.reference_data.claim_request = {
        "request_id": str(REQUEST_ID),
        "client_id": 1001,
        "request_status": "submitted",
        "client_data": {
            "full_name": "Ion Popescu",
            "email": "ion@example.test",
            "phone": "+40700000000",
        },
        "claim_data": {
            "claim_type": "Fire",
            "incident_date": "2026-05-01",
            "incident_time": "10:30",
            "description": "" if missing_description else "Kitchen fire with smoke damage to walls.",
            "estimated_damage": 12000,
            "coverage_amount": 100000,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "contact_phone": "+40700000000",
            "contact_email": "ion@example.test",
            "emergency_services": True,
        },
        "attachments": [
            {
                "file_name": "damage_photo.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 100,
                "metadata": {"label": "Photos from incident"},
            },
            {
                "file_name": "invoice.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "metadata": {"label": "Documents"},
            },
        ],
    }
    context.reference_data.extracted_documents = ExtractedDocumentBundle(
        source="test",
        documents=[
            ExtractedClaimDocument(
                document_id="doc:photos-from-incident.pdf",
                filename="photos-from-incident.pdf",
                document_type="incident_photos",
                extracted_fields={
                    "damage_type": "fire damage",
                    "authority_verified": True,
                },
                extraction_confidence=0.9,
                source="test",
            )
        ],
    )
    return context


def test_claim_modules_build_review_view_from_valid_context() -> None:
    context = make_context()

    results = [
        ClaimValidationModule().evaluate(context),
        ClaimClassificationModule().evaluate(context),
        ClaimSummaryModule().evaluate(context),
        CoverageAssessmentModule().evaluate(context),
        DocumentConsistencyModule().evaluate(context),
        EvidenceRequirementModule().evaluate(context),
        ClaimReviewScreenBuilderModule().build(context),
    ]

    assert [result.status for result in results] == ["success"] * 7
    assert context.generated_outputs.validation is not None
    assert context.generated_outputs.classification is not None
    assert context.generated_outputs.summary is not None
    assert context.generated_outputs.coverage_assessment is not None
    assert context.generated_outputs.document_consistency is not None
    assert context.generated_outputs.evidence_requirements is not None
    assert context.review_state.claim_review_view is not None
    assert context.review_state.claim_review_view.coverage_assessment is not None
    assert (
        context.review_state.claim_review_view.suggested_next_action
        == "underwriter_review"
    )
    assert context.review_state.claim_review_view.confidence_panel["score"] is None


def test_validation_fails_when_required_claim_data_is_missing() -> None:
    context = make_context(missing_description=True)

    result = ClaimValidationModule().evaluate(context)

    assert result.status == "failed"
    assert context.generated_outputs.validation is not None
    assert "claim_data.description" in (
        context.generated_outputs.validation.missing_required_fields
    )


def test_confidence_penalizes_missing_document_evidence() -> None:
    context = make_context()
    context.reference_data.claim_request["attachments"] = [
        context.reference_data.claim_request["attachments"][0]
    ]

    ClaimValidationModule().evaluate(context)
    ClaimClassificationModule().evaluate(context)
    ClaimSummaryModule().evaluate(context)
    result = ClaimConfidenceModule().evaluate(context)

    assert result.status == "success"
    assert context.generated_outputs.confidence is not None
    assert context.generated_outputs.confidence.score == 75
    assert "No supporting document attachment was found." in (
        context.generated_outputs.confidence.rationale
    )
