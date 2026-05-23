from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from underwright.application.services.claim_attachment_processing_service import (
    ClaimAttachmentProcessingService,
)
from underwright.application.services.claim_precheck_policy_service import (
    ClaimPrecheckPolicyConfig,
    ClaimPrecheckPolicyService,
)
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest

REQUEST_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def make_claim(
    *,
    file_name: str = "damage-report.pdf",
    content_type: str = "application/pdf",
    document_role: str = "property_photo_after",
) -> ClaimRequest:
    return ClaimRequest(
        request_id=REQUEST_ID,
        client_id=1001,
        request_status="submitted",
        client_data={"full_name": "Ion Popescu"},
        claim_data={"claim_type": "Fire", "estimated_damage": 12000},
        attachments=[
            ClaimAttachmentMetadata(
                file_name=file_name,
                content_type=content_type,
                size_bytes=123,
                file_url=f"/claims/{REQUEST_ID}/attachments/attachment-1",
                metadata={
                    "attachment_id": "attachment-1",
                    "storage_key": "attachment-1",
                    "document_role": document_role,
                },
            )
        ],
        created_at=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
    )


class FakeClaimRequestService:
    def __init__(self, claim: ClaimRequest) -> None:
        self.claim = claim
        self.updated_statuses: list[str | None] = []

    def get_claim_request_detail(self, request_id: UUID) -> ClaimRequest:
        assert request_id == self.claim.request_id
        return self.claim

    def count_client_claims_since(self, client_id, since) -> int:
        return 0

    def update_request_claim_data(
        self,
        request_id: UUID,
        claim_data: dict,
        request_status: str | None = None,
    ) -> ClaimRequest:
        assert request_id == self.claim.request_id
        self.updated_statuses.append(request_status)
        self.claim = self.claim.model_copy(
            update={
                "claim_data": claim_data,
                "request_status": request_status or self.claim.request_status,
            }
        )
        return self.claim

    def update_request_attachments(self, request_id: UUID, attachments: list) -> ClaimRequest:
        assert request_id == self.claim.request_id
        self.claim = self.claim.model_copy(
            update={
                "attachments": [
                    ClaimAttachmentMetadata.model_validate(item) for item in attachments
                ]
            }
        )
        return self.claim


class FakeStorageService:
    pass


class FakeTextExtractor:
    def extract_texts(self, claim_request: ClaimRequest, storage) -> list[dict]:
        return [
            {
                "file_name": claim_request.attachments[0].file_name,
                "content_type": claim_request.attachments[0].content_type,
                "text": "Policy number PAD-001. Claim number CL-001. Damage amount 12000 RON.",
                "error": None,
            }
        ]


class FakeSummaryGenerator:
    def __init__(self) -> None:
        self.claim_context: dict | None = None

    def summarize(
        self,
        extraction_results: list[dict],
        *,
        claim_context: dict | None = None,
    ) -> dict:
        self.claim_context = claim_context
        return {
            "summary": "Uploaded evidence references PAD-001 and damage amount 12000 RON.",
            "key_info": {},
            "error": None,
        }


def make_service(claim: ClaimRequest) -> tuple[ClaimAttachmentProcessingService, FakeClaimRequestService]:
    claim_service = FakeClaimRequestService(claim)
    summary_generator = FakeSummaryGenerator()
    service = ClaimAttachmentProcessingService(
        claim_request_service=claim_service,
        storage_service=FakeStorageService(),
        precheck_policy_service=ClaimPrecheckPolicyService(
            ClaimPrecheckPolicyConfig(
                required_document_roles=(
                    "identity_document",
                    "bank_document",
                )
            )
        ),
        text_extractor=FakeTextExtractor(),
        summary_generator=summary_generator,
    )
    return service, claim_service


def test_processing_stores_summary_and_attachment_metadata() -> None:
    service, claim_service = make_service(make_claim())

    processed = service.process_request_attachments(REQUEST_ID)

    assert service.summary_generator.claim_context == {
        "claim_type": "Fire",
        "estimated_damage": 12000,
    }
    assert processed.claim_data["attachment_extraction_summary"]["summary"] == (
        "Uploaded evidence references PAD-001 and damage amount 12000 RON."
    )
    assert processed.claim_data["attachment_extraction_summary"]["claim_request_id"] == str(
        REQUEST_ID
    )
    assert processed.claim_data["attachment_extraction_summary"]["attachment_keys"] == [
        "attachment-1"
    ]
    assert processed.claim_data["attachment_extraction_summary"]["attachment_count"] == 1
    attachment_metadata = processed.attachments[0].metadata
    assert attachment_metadata["extraction_status"] == "completed"
    assert attachment_metadata["extraction_summary_path"] == (
        "claim_data.attachment_extraction_summary.summary"
    )
    assert "Policy number" in attachment_metadata["extracted_text"]
    assert "precheck_rejected" not in claim_service.updated_statuses


def test_processing_skips_optional_legal_documents_for_ai_extraction() -> None:
    claim = make_claim().model_copy(
        update={
            "attachments": [
                ClaimAttachmentMetadata(
                    file_name="bank-document.pdf",
                    content_type="application/pdf",
                    size_bytes=123,
                    file_url=f"/claims/{REQUEST_ID}/attachments/attachment-bank",
                    metadata={
                        "attachment_id": "attachment-bank",
                        "storage_key": "attachment-bank",
                        "document_role": "bank_document",
                    },
                ),
                ClaimAttachmentMetadata(
                    file_name="incident-photo.jpg",
                    content_type="image/jpeg",
                    size_bytes=123,
                    file_url=f"/claims/{REQUEST_ID}/attachments/attachment-photo",
                    metadata={
                        "attachment_id": "attachment-photo",
                        "storage_key": "attachment-photo",
                        "document_role": "property_photo_after",
                    },
                ),
            ]
        }
    )
    service, _ = make_service(claim)

    processed = service.process_request_attachments(REQUEST_ID)

    optional_metadata = processed.attachments[0].metadata
    evidence_metadata = processed.attachments[1].metadata
    assert optional_metadata["extraction_status"] == "skipped"
    assert optional_metadata["extraction_skip_reason"] == "optional_legal_document"
    assert optional_metadata["extracted_text"] == ""
    assert evidence_metadata["extraction_status"] == "completed"
    assert "Policy number" in evidence_metadata["extracted_text"]


def test_processing_preserves_claim_photo_analysis_highlights() -> None:
    service, _ = make_service(make_claim())

    highlights = service._summarize_attachment_text_highlights(
        "\n".join(
            [
                "- Visible damage: dark staining and warped wall panels are visible.",
                "- Affected area: interior room wall and lower floor area.",
                "- Damage severity: unclear from this single photo.",
                "- Readable text: no readable labels visible.",
                "- Photo uncertainty: image does not show the full room.",
            ]
        )
    )

    assert "- Visible damage: dark staining and warped wall panels are visible." in highlights
    assert "- Affected area: interior room wall and lower floor area." in highlights
    assert "- Photo uncertainty: image does not show the full room." in highlights
    assert "Policy number" not in highlights


def test_missing_required_documents_creates_review_precheck_without_rejection() -> None:
    service, claim_service = make_service(make_claim())

    processed = service.process_request_attachments(REQUEST_ID)

    precheck = processed.claim_data["precheck_policy_decision"]
    assert precheck["status"] == "review"
    assert processed.request_status == "submitted"
    assert "precheck_rejected" not in claim_service.updated_statuses


def test_unrelated_image_precheck_blocks_processing_and_marks_rejected() -> None:
    claim = make_claim(
        file_name="cat-photo.jpg",
        content_type="image/jpeg",
        document_role="",
    )
    service, claim_service = make_service(claim)

    processed = service.process_request_attachments(REQUEST_ID)

    assert processed.request_status == "precheck_rejected"
    assert "precheck_rejected" in claim_service.updated_statuses
    assert processed.claim_data["precheck_policy_decision"]["status"] == "reject"
    assert processed.attachments[0].metadata["extraction_status"] == "blocked"
