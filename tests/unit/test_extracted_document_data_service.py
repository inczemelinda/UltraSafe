from __future__ import annotations

from uuid import UUID

from underwright.application.services.extracted_document_data_service import (
    AttachmentMetadataDocumentExtractor,
    DemoFilenameClaimDocumentExtractor,
    ExtractedDocumentDataService,
)
from underwright.composition import build_extracted_document_data_service
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest


REQUEST_ID = UUID("70000000-0000-0000-0000-000000000001")


class FakeClaimRequestService:
    def __init__(self, request: ClaimRequest) -> None:
        self.request = request
        self.request_ids: list[UUID] = []

    def get_claim_request_detail(self, request_id: UUID) -> ClaimRequest:
        self.request_ids.append(request_id)
        return self.request


def test_normal_mode_does_not_infer_authoritative_facts_from_filenames() -> None:
    request = make_request(
        [
            attachment("id-document.pdf"),
            attachment("property-ownership-document.pdf"),
            attachment("photos-from-incident.pdf"),
        ]
    )
    service = ExtractedDocumentDataService(FakeClaimRequestService(request))

    bundle = service.get_extracted_documents(str(REQUEST_ID))

    assert bundle.source == "attachment_extraction_metadata"
    assert bundle.extraction_provenance == "actual"
    assert bundle.extraction_status == "unavailable"
    assert [document.filename for document in bundle.documents] == [
        "photos-from-incident.pdf",
    ]
    assert [document.document_type for document in bundle.documents] == [
        "unknown",
    ]
    assert all(document.extracted_fields == {} for document in bundle.documents)
    assert all(document.extraction_confidence == 0 for document in bundle.documents)
    assert all(
        document.extraction_provenance == "unavailable"
        for document in bundle.documents
    )
    assert "manual review" in bundle.documents[0].extraction_message.lower()


def test_actual_extraction_metadata_is_returned_with_provenance() -> None:
    request = make_request(
        [
            attachment(
                "damage-report.pdf",
                file_url=f"/claims/{REQUEST_ID}/attachments/attachment-damage",
                metadata={
                    "attachment_id": "attachment-damage",
                    "storage_key": "claims/damage-report.pdf",
                    "document_role": "repair_estimate",
                    "extraction_status": "completed",
                    "extracted_text": "- Policy number: PAD-001\n- Amount: 100000 RON",
                    "extracted_text_source": "attachment_extraction_highlights",
                    "extracted_at": "2026-05-16T10:00:00Z",
                },
            )
        ]
    )
    service = ExtractedDocumentDataService(FakeClaimRequestService(request))

    bundle = service.get_extracted_documents(str(REQUEST_ID))

    document = bundle.documents[0]
    assert bundle.extraction_status == "completed"
    assert document.document_type == "repair_estimate"
    assert document.extraction_provenance == "actual"
    assert document.extraction_status == "completed"
    assert document.source == "attachment_extraction_metadata"
    assert document.extracted_fields["policy_number"] == "PAD-001"
    assert document.extracted_fields["amount"] == "100000 RON"
    assert document.extraction_confidence == 0.75
    assert document.extraction_metadata["attachment_id"] == "attachment-damage"
    assert document.extraction_metadata["storage_key"] == "claims/damage-report.pdf"
    assert document.extraction_metadata["file_url"] == (
        f"/claims/{REQUEST_ID}/attachments/attachment-damage"
    )


def test_explicit_demo_mode_can_use_filename_based_extraction() -> None:
    request = make_request(
        [
            attachment("id-document.pdf"),
            attachment("property-ownership-document.pdf"),
            attachment("photos-from-incident.pdf"),
        ]
    )
    service = ExtractedDocumentDataService(
        FakeClaimRequestService(request),
        extractor=DemoFilenameClaimDocumentExtractor(),
    )

    bundle = service.get_extracted_documents(str(REQUEST_ID))

    assert [document.document_type for document in bundle.documents] == [
        "incident_photos",
    ]
    assert bundle.source == "demo_mock_filename_adapter"
    assert bundle.extraction_provenance == "demo_mock"
    assert bundle.documents[0].extracted_fields["visible_damage"] is True
    assert bundle.documents[0].extraction_provenance == "demo_mock"
    assert bundle.documents[0].extraction_metadata["demo_mock"] is True


def test_optional_legal_documents_are_excluded_from_claim_analysis_bundle() -> None:
    request = make_request(
        [
            attachment(
                "bank-document.pdf",
                metadata={"document_role": "bank_document", "label": "Bank document"},
            ),
            attachment(
                "incident-photo.jpg",
                metadata={"document_role": "property_photo_after", "label": "Photos from incident"},
            ),
        ]
    )
    service = ExtractedDocumentDataService(FakeClaimRequestService(request))

    bundle = service.get_extracted_documents(str(REQUEST_ID))

    assert [document.filename for document in bundle.documents] == ["incident-photo.jpg"]


def test_additional_attachments_preserve_unavailable_state() -> None:
    fake_claim_request_service = FakeClaimRequestService(
        make_request([attachment("invoice.pdf")])
    )
    service = ExtractedDocumentDataService(fake_claim_request_service)

    bundle = service.get_extracted_documents(
        str(REQUEST_ID),
        additional_attachments=[attachment("PROPERTY_PHOTOS.PDF")],
    )

    assert fake_claim_request_service.request_ids == [REQUEST_ID]
    assert len(bundle.documents) == 2
    assert bundle.documents[0].document_type == "unknown"
    assert bundle.documents[0].extraction_status == "unavailable"
    assert bundle.documents[1].filename == "PROPERTY_PHOTOS.PDF"
    assert bundle.documents[1].extraction_confidence == 0


def test_composition_requires_explicit_demo_extraction_flag(monkeypatch) -> None:
    claim_request_service = FakeClaimRequestService(make_request([]))

    monkeypatch.delenv("UNDERWRIGHT_CLAIM_DOCUMENT_DEMO_EXTRACTION", raising=False)
    normal_service = build_extracted_document_data_service(claim_request_service)
    assert isinstance(normal_service.extractor, AttachmentMetadataDocumentExtractor)

    monkeypatch.setenv("UNDERWRIGHT_CLAIM_DOCUMENT_DEMO_EXTRACTION", "true")
    demo_service = build_extracted_document_data_service(claim_request_service)
    assert isinstance(demo_service.extractor, DemoFilenameClaimDocumentExtractor)


def attachment(
    filename: str,
    *,
    file_url: str | None = None,
    metadata: dict | None = None,
) -> ClaimAttachmentMetadata:
    return ClaimAttachmentMetadata(
        file_name=filename,
        content_type="application/pdf",
        size_bytes=100,
        file_url=file_url,
        metadata=metadata or {"label": "Mock document"},
    )


def make_request(attachments: list[ClaimAttachmentMetadata]) -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status="submitted",
        client_data={"full_name": "Ion Popescu"},
        claim_data={
            "claim_type": "Storm",
            "incident_date": "2026-05-01",
            "policy_number": "PAD-001",
            "property_address": "Bucharest",
            "coverage_amount": 100000,
        },
        attachments=attachments,
    )
