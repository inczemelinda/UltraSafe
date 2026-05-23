from __future__ import annotations

from uuid import UUID

from underwright.domain.claim_analysis import (
    ClaimReviewFindings,
    CoverageAssessmentResult,
    DocumentConsistencyResult,
    DocumentDiscrepancy,
    DocumentSupportingFact,
    EvidenceRequirement,
    EvidenceRequirementResult,
    EvidenceRequestDraft,
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
)
from underwright.domain.claim_case_context import ClaimCaseContext


DOCUMENT_ID = UUID("30000000-0000-0000-0000-000000000001")


def test_extracted_document_bundle_serializes_and_deserializes() -> None:
    bundle = ExtractedDocumentBundle(
        source="temporary_mock_service",
        documents=[
            ExtractedClaimDocument(
                document_id=DOCUMENT_ID,
                filename="invoice.pdf",
                document_type="repair_invoice",
                extracted_fields={
                    "incident_date": "2026-05-01",
                    "estimated_damage": 12000,
                },
                extraction_confidence=0.91,
                source="temporary_mock_service",
            )
        ],
    )

    serialized = bundle.model_dump(mode="json")
    hydrated = ExtractedDocumentBundle.model_validate(serialized)

    assert serialized["documents"][0]["document_id"] == str(DOCUMENT_ID)
    assert hydrated.documents[0].filename == "invoice.pdf"
    assert hydrated.documents[0].extracted_fields["estimated_damage"] == 12000
    assert hydrated.documents[0].extraction_confidence == 0.91


def test_claim_review_findings_serializes_and_deserializes() -> None:
    findings = ClaimReviewFindings(
        coverage_assessment=CoverageAssessmentResult(
            coverage_status="potentially_covered",
            matched_wording_sections=["PAD section 4.2"],
            wording_section_ids=["PAD section 4.2", "PAD exclusion 7.1"],
            possible_exclusions=["pre-existing damage"],
            rationale="The reported incident appears related to covered property damage.",
            confidence="medium",
        ),
        document_consistency=DocumentConsistencyResult(
            supporting_facts=[
                DocumentSupportingFact(
                    field="incident_date",
                    claim_value="2026-05-01",
                    document_value="2026-05-01",
                    source_document=DOCUMENT_ID,
                    severity="low",
                    message="The invoice date matches the claim incident date.",
                )
            ],
            discrepancies=[
                DocumentDiscrepancy(
                    field="estimated_damage",
                    claim_value=12000,
                    document_value=9500,
                    source_document="invoice.pdf",
                    severity="medium",
                    message="The claimed amount is higher than the invoice total.",
                )
            ],
        ),
        evidence_requirements=EvidenceRequirementResult(
            requirements=[
                EvidenceRequirement(
                    requirement_type="repair_invoice",
                    reason="The claim amount needs support from repair documentation.",
                    acceptable_documents=["repair_invoice", "contractor_estimate"],
                    severity="high",
                    status="insufficient",
                    suggested_next_action="Request an itemized repair invoice.",
                )
            ],
            suggested_next_action="request_evidence",
        ),
        suggested_next_action="Prepare for human review with evidence follow-up.",
        human_readable_summary=(
            "Coverage may apply, but the damage amount needs stronger evidence."
        ),
    )

    serialized = findings.model_dump(mode="json")
    hydrated = ClaimReviewFindings.model_validate(serialized)

    assert serialized["coverage_assessment"]["coverage_status"] == (
        "potentially_covered"
    )
    assert serialized["coverage_assessment"]["wording_section_ids"] == [
        "PAD section 4.2",
        "PAD exclusion 7.1",
    ]
    assert "assessed_at" in serialized["coverage_assessment"]
    assert serialized["document_consistency"]["supporting_facts"][0][
        "source_document"
    ] == str(DOCUMENT_ID)
    assert hydrated.document_consistency.discrepancies[0].severity == "medium"
    assert (
        hydrated.evidence_requirements.requirements[0].suggested_next_action
        == "Request an itemized repair invoice."
    )
    assert hydrated.evidence_requirements.suggested_next_action == "request_evidence"
    assert hydrated.human_readable_summary is not None


def test_claim_review_output_keeps_old_fields_and_accepts_findings() -> None:
    context = ClaimCaseContext()
    context.generated_outputs.claim_review.review_summary = "Legacy summary remains."
    context.generated_outputs.claim_review.recommendation = "review"
    context.generated_outputs.claim_review.findings = ClaimReviewFindings(
        suggested_next_action="Request additional documents.",
        human_readable_summary="Evidence is incomplete.",
    )

    serialized = context.model_dump(mode="json")
    hydrated = ClaimCaseContext.model_validate(serialized)

    claim_review = serialized["generated_outputs"]["claim_review"]
    assert claim_review["review_summary"] == "Legacy summary remains."
    assert claim_review["recommendation"] == "review"
    assert claim_review["findings"]["suggested_next_action"] == (
        "Request additional documents."
    )
    assert hydrated.generated_outputs.claim_review.findings is not None
    assert (
        hydrated.generated_outputs.claim_review.findings.human_readable_summary
        == "Evidence is incomplete."
    )


def test_evidence_request_draft_serializes_and_deserializes() -> None:
    draft = EvidenceRequestDraft(
        claim_request_id=DOCUMENT_ID,
        subject="Additional evidence required for your fire claim",
        body="Please provide a fire service report.",
        required_documents=["fire service report"],
        status="draft",
    )

    serialized = draft.model_dump(mode="json")
    hydrated = EvidenceRequestDraft.model_validate(serialized)

    assert serialized["claim_request_id"] == str(DOCUMENT_ID)
    assert serialized["status"] == "draft"
    assert "created_at" in serialized
    assert hydrated.required_documents == ["fire service report"]
