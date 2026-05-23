from __future__ import annotations

from uuid import UUID

from underwright.application.modules.evidence_requirement_module import (
    EvidenceRequirementModule,
)
from underwright.domain.claim_analysis import (
    DocumentConsistencyResult,
    DocumentDiscrepancy,
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
)
from underwright.domain.claim_case_context import ClaimCaseContext


REQUEST_ID = UUID("81000000-0000-0000-0000-000000000001")


def test_fire_claim_without_official_report_requests_fire_confirmation() -> None:
    context = make_context(
        claim_type="Fire",
        emergency_services=False,
        documents=[
            make_document(
                "photos-from-incident.pdf",
                "incident_photos",
                {"damage_type": "fire damage"},
            )
        ],
    )

    result = EvidenceRequirementModule().evaluate(context)

    evidence_result = context.generated_outputs.evidence_requirements
    assert result.status == "success"
    assert evidence_result is not None
    assert evidence_result.suggested_next_action == "request_evidence"
    assert evidence_result.required_evidence[0].requirement_type == (
        "official_fire_incident_confirmation"
    )
    acceptable_documents = evidence_result.required_evidence[0].acceptable_documents
    assert "fire_service_report" in acceptable_documents


def test_fire_claim_with_authority_verified_document_needs_no_extra_evidence() -> None:
    context = make_context(
        claim_type="Fire",
        emergency_services=False,
        documents=[
            make_document(
                "official-report.pdf",
                "incident_photos",
                {
                    "damage_type": "fire damage",
                    "authority_verified": True,
                },
            )
        ],
    )

    EvidenceRequirementModule().evaluate(context)

    evidence_result = context.generated_outputs.evidence_requirements
    assert evidence_result is not None
    assert evidence_result.required_evidence == []
    assert evidence_result.suggested_next_action == "underwriter_review"


def test_short_description_requires_additional_incident_details() -> None:
    context = make_context(
        claim_type="Theft",
        description="Too short",
        documents=[],
    )

    EvidenceRequirementModule().evaluate(context)

    evidence_result = context.generated_outputs.evidence_requirements
    assert evidence_result is not None
    assert evidence_result.suggested_next_action == "request_evidence"
    assert evidence_result.required_evidence[0].requirement_type == (
        "additional_incident_details"
    )


def test_high_document_discrepancy_sets_manual_review_action() -> None:
    context = make_context(claim_type="Theft", documents=[])
    context.generated_outputs.document_consistency = DocumentConsistencyResult(
        status="discrepancies_found",
        discrepancies=[
            DocumentDiscrepancy(
                field="estimated_damage",
                claim_value=150000,
                document_value=100000,
                source_document="policy-document.pdf",
                severity="high",
                message="Estimated damage exceeds the policy coverage limit.",
            )
        ],
    )

    EvidenceRequirementModule().evaluate(context)

    evidence_result = context.generated_outputs.evidence_requirements
    assert evidence_result is not None
    assert evidence_result.suggested_next_action == "manual_review"
    assert evidence_result.required_evidence == []
    assert "High-severity document discrepancies" in evidence_result.rationale


def make_context(
    *,
    claim_type: str,
    documents: list[ExtractedClaimDocument],
    description: str = "Detailed incident description with enough useful facts.",
    emergency_services: bool | str = True,
) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.reference_data.claim_request = {
        "request_id": str(REQUEST_ID),
        "client_id": 1001,
        "client_data": {"full_name": "Ion Popescu"},
        "claim_data": {
            "claim_type": claim_type,
            "description": description,
            "emergency_services": emergency_services,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "estimated_damage": 12000,
        },
        "attachments": [],
    }
    context.reference_data.extracted_documents = ExtractedDocumentBundle(
        source="test",
        documents=documents,
    )
    context.generated_outputs.document_consistency = DocumentConsistencyResult(
        status="no_discrepancies"
    )
    return context


def make_document(
    filename: str,
    document_type: str,
    extracted_fields: dict,
) -> ExtractedClaimDocument:
    return ExtractedClaimDocument(
        document_id=f"doc:{filename}",
        filename=filename,
        document_type=document_type,
        extracted_fields=extracted_fields,
        extraction_confidence=0.9,
        source="test",
    )
