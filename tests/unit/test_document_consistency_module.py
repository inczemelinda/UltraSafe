from __future__ import annotations

from uuid import UUID

from underwright.application.modules.document_consistency_module import (
    DocumentConsistencyModule,
)
from underwright.domain.claim_analysis import (
    ExtractedClaimDocument,
    ExtractedDocumentBundle,
)
from underwright.domain.claim_case_context import ClaimCaseContext


REQUEST_ID = UUID("80000000-0000-0000-0000-000000000001")


def test_document_consistency_reports_supporting_facts_when_all_fields_match() -> None:
    context = make_context(
        documents=[
            make_document(
                "policy-document.pdf",
                "policy_document",
                {
                    "policy_number": "PAD-001",
                    "insured_address": "Bucharest",
                    "coverage_limit": 100000,
                },
            ),
            make_document(
                "land-registry-extract.pdf",
                "land_registry_extract",
                {"property_address": "Bucharest"},
            ),
            make_document(
                "property-ownership-document.pdf",
                "property_ownership",
                {
                    "property_address": "Bucharest",
                    "owner_name": "Ion Popescu",
                },
            ),
            make_document(
                "id-document.pdf",
                "id_document",
                {"full_name": "Ion Popescu"},
            ),
        ]
    )

    result = DocumentConsistencyModule().evaluate(context)

    consistency = context.generated_outputs.document_consistency
    assert result.status == "success"
    assert consistency is not None
    assert consistency.status == "no_discrepancies"
    assert consistency.discrepancies == []
    assert {fact.field for fact in consistency.supporting_facts} >= {
        "policy_number",
        "property_address",
        "full_name",
        "estimated_damage",
    }
    assert (
        context.generated_outputs.claim_review.findings.document_consistency
        == consistency
    )


def test_document_consistency_reports_address_mismatch() -> None:
    context = make_context(
        documents=[
            make_document(
                "property-ownership-document.pdf",
                "property_ownership",
                {
                    "property_address": "Cluj-Napoca",
                    "owner_name": "Ion Popescu",
                },
            )
        ]
    )

    DocumentConsistencyModule().evaluate(context)

    consistency = context.generated_outputs.document_consistency
    assert consistency is not None
    assert consistency.status == "discrepancies_found"
    discrepancy = consistency.discrepancies[0]
    assert discrepancy.field == "property_address"
    assert discrepancy.claim_value == "Bucharest"
    assert discrepancy.document_value == "Cluj-Napoca"
    assert discrepancy.severity == "high"


def test_document_consistency_reports_policy_number_mismatch() -> None:
    context = make_context(
        documents=[
            make_document(
                "policy-document.pdf",
                "policy_document",
                {
                    "policy_number": "PAD-999",
                    "insured_address": "Bucharest",
                    "coverage_limit": 100000,
                },
            )
        ]
    )

    DocumentConsistencyModule().evaluate(context)

    consistency = context.generated_outputs.document_consistency
    assert consistency is not None
    assert consistency.status == "discrepancies_found"
    policy_discrepancy = next(
        discrepancy
        for discrepancy in consistency.discrepancies
        if discrepancy.field == "policy_number"
    )
    assert policy_discrepancy.claim_value == "PAD-001"
    assert policy_discrepancy.document_value == "PAD-999"


def test_document_consistency_handles_missing_extracted_documents() -> None:
    context = make_context(documents=[])

    result = DocumentConsistencyModule().evaluate(context)

    consistency = context.generated_outputs.document_consistency
    assert result.status == "success"
    assert consistency is not None
    assert consistency.status == "insufficient_document_data"
    assert consistency.supporting_facts == []
    assert consistency.discrepancies == []


def test_document_consistency_uses_incident_photos_to_support_fire_damage() -> None:
    context = make_context(
        claim_type="Fire",
        documents=[
            make_document(
                "photos-from-incident.pdf",
                "incident_photos",
                {"damage_type": "fire damage"},
            )
        ],
    )

    DocumentConsistencyModule().evaluate(context)

    consistency = context.generated_outputs.document_consistency
    assert consistency is not None
    assert consistency.status == "no_discrepancies"
    incident_fact = next(
        fact
        for fact in consistency.supporting_facts
        if fact.field == "incident_type"
    )
    assert incident_fact.claim_value == "Fire"
    assert incident_fact.document_value == "fire damage"


def make_context(
    *,
    documents: list[ExtractedClaimDocument],
    claim_type: str = "Storm",
) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.reference_data.claim_request = {
        "request_id": str(REQUEST_ID),
        "client_id": 1001,
        "client_data": {"full_name": "Ion Popescu"},
        "claim_data": {
            "claim_type": claim_type,
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "estimated_damage": 12000,
        },
        "attachments": [],
    }
    context.reference_data.client_profile = {"full_name": "Ion Popescu"}
    context.reference_data.extracted_documents = ExtractedDocumentBundle(
        source="test",
        documents=documents,
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
