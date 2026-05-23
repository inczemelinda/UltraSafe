from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_case_context_service,
    get_claim_attachment_processing_service,
    get_claim_attachment_storage_service,
    get_claim_request_service,
    get_email_read_service,
    get_evidence_refresh_workflow,
)
from underwright.api.main import create_app
from underwright.domain.claim_analysis import EvidenceRequestDraft
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest
from underwright.domain.email_message import EmailMessage


REQUEST_ID = UUID("157b7057-acee-4ad4-9617-84fa4b86574d")
REPLY_TOKEN = "reply-token-123"


def test_postmark_inbound_webhook_records_email_attachments_and_refreshes(
    monkeypatch,
) -> None:
    app, fakes = _app_with_fakes(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/webhooks/postmark/inbound",
        auth=("postmark", "secret"),
        json=_postmark_payload(),
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "processed"
    assert payload["request_id"] == str(REQUEST_ID)
    assert payload["attachment_count"] == 1
    assert payload["refresh_status"] == "completed"
    assert fakes.claim_service.claim_request.attachments
    attachment = fakes.claim_service.claim_request.attachments[0]
    assert attachment.file_name == "fire-report.pdf"
    assert attachment.metadata["source"] == "email_hook"
    assert attachment.metadata["sender_email"] == "client@example.test"
    assert attachment.metadata["subject"] == (
        "Re: [UW-CLAIM:reply-token-123] Additional evidence required"
    )
    assert attachment.metadata["provider_message_id"] == "postmark-message-1"
    assert attachment.metadata["reply_token"] == REPLY_TOKEN
    assert fakes.processing_service.processed_request_ids == [REQUEST_ID]
    assert fakes.refresh_workflow.request_ids == [REQUEST_ID]
    assert fakes.email_service.saved[0].direction == "INBOUND"
    assert fakes.email_service.saved[0].status == "RECEIVED"


def test_postmark_inbound_webhook_requires_basic_auth(monkeypatch) -> None:
    app, _fakes = _app_with_fakes(monkeypatch)
    client = TestClient(app)

    missing = client.post("/webhooks/postmark/inbound", json=_postmark_payload())
    wrong = client.post(
        "/webhooks/postmark/inbound",
        auth=("postmark", "wrong"),
        json=_postmark_payload(),
    )

    assert missing.status_code == 401
    assert wrong.status_code == 403


def test_postmark_inbound_webhook_ignores_unmatched_reply_token(monkeypatch) -> None:
    app, fakes = _app_with_fakes(monkeypatch, reply_token="different-token")
    client = TestClient(app)

    response = client.post(
        "/webhooks/postmark/inbound",
        auth=("postmark", "secret"),
        json=_postmark_payload(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert fakes.claim_service.claim_request.attachments == []
    assert fakes.email_service.saved == []


def test_postmark_inbound_webhook_is_idempotent_by_message_id(monkeypatch) -> None:
    existing_email = EmailMessage(
        id=uuid4(),
        case_id=REQUEST_ID,
        request_id=REQUEST_ID,
        direction="INBOUND",
        from_email="client@example.test",
        to_email="claims@example.test",
        subject="Already processed",
        body="Already processed.",
        status="RECEIVED",
        provider_message_id="postmark-message-1",
    )
    app, fakes = _app_with_fakes(monkeypatch, existing_emails=[existing_email])
    client = TestClient(app)

    response = client.post(
        "/webhooks/postmark/inbound",
        auth=("postmark", "secret"),
        json=_postmark_payload(),
    )

    assert response.status_code == 200
    assert response.json()["duplicate"] is True
    assert fakes.claim_service.claim_request.attachments == []
    assert fakes.processing_service.processed_request_ids == []


def test_postmark_inbound_webhook_skips_malformed_attachment(monkeypatch) -> None:
    app, fakes = _app_with_fakes(monkeypatch)
    client = TestClient(app)

    payload = _postmark_payload()
    payload["Attachments"][0]["Content"] = "not-base64!"
    response = client.post(
        "/webhooks/postmark/inbound",
        auth=("postmark", "secret"),
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["attachment_count"] == 0
    assert response.json()["skipped_attachment_count"] == 1
    assert fakes.claim_service.claim_request.attachments == []
    assert fakes.email_service.saved[0].provider_message_id == "postmark-message-1"


def _app_with_fakes(
    monkeypatch,
    *,
    reply_token: str = REPLY_TOKEN,
    existing_emails: list[EmailMessage] | None = None,
):
    monkeypatch.setenv("POSTMARK_WEBHOOK_USERNAME", "postmark")
    monkeypatch.setenv("POSTMARK_WEBHOOK_PASSWORD", "secret")
    context = _claim_context(reply_token)
    fakes = SimpleNamespace(
        case_context_service=FakeCaseContextService(context, reply_token),
        claim_service=FakeClaimRequestService(),
        storage_service=FakeClaimAttachmentStorageService(),
        processing_service=FakeClaimAttachmentProcessingService(),
        refresh_workflow=FakeEvidenceRefreshWorkflow(),
        email_service=FakeInboundEmailService(existing_emails or []),
    )
    app = create_app()
    app.dependency_overrides[get_case_context_service] = (
        lambda: fakes.case_context_service
    )
    app.dependency_overrides[get_claim_request_service] = lambda: fakes.claim_service
    app.dependency_overrides[get_claim_attachment_storage_service] = (
        lambda: fakes.storage_service
    )
    app.dependency_overrides[get_claim_attachment_processing_service] = (
        lambda: fakes.processing_service
    )
    app.dependency_overrides[get_evidence_refresh_workflow] = (
        lambda: fakes.refresh_workflow
    )
    app.dependency_overrides[get_email_read_service] = lambda: fakes.email_service
    return app, fakes


def _claim_context(reply_token: str) -> ClaimCaseContext:
    context = ClaimCaseContext(source_inputs={"request_id": REQUEST_ID})
    context.generated_outputs.evidence_request_draft = EvidenceRequestDraft(
        draft_id="draft-1",
        claim_request_id=REQUEST_ID,
        subject="Additional evidence required",
        body="Please send the fire report.",
        recipients=["client@example.test"],
        required_documents=["fire report"],
        reply_token=reply_token,
    )
    return context


def _postmark_payload() -> dict:
    return {
        "MessageID": "postmark-message-1",
        "From": "Client <client@example.test>",
        "FromFull": {"Email": "client@example.test"},
        "To": "claims+reply-token-123@inbound.underwright.example",
        "ToFull": [
            {
                "Email": "claims+reply-token-123@inbound.underwright.example",
                "MailboxHash": REPLY_TOKEN,
            }
        ],
        "Subject": "Re: [UW-CLAIM:reply-token-123] Additional evidence required",
        "TextBody": "Attached is the fire report.",
        "Attachments": [
            {
                "Name": "fire-report.pdf",
                "ContentType": "application/pdf",
                "Content": base64.b64encode(b"%PDF demo").decode("ascii"),
            }
        ],
    }


class FakeCaseContextService:
    def __init__(self, context: ClaimCaseContext, reply_token: str) -> None:
        self.context = context
        self.reply_token = reply_token

    def get_latest_claim_case_context_by_evidence_reply_token(
        self,
        reply_token: str,
    ) -> ClaimCaseContext:
        if reply_token != self.reply_token:
            raise ValueError("ClaimCaseContext not found")
        return self.context


class FakeClaimRequestService:
    def __init__(self) -> None:
        self.claim_request = ClaimRequest(
            request_id=REQUEST_ID,
            client_id=1001,
            request_status="in_review",
            client_data={"email": "client@example.test"},
            claim_data={"claim_type": "Fire"},
            attachments=[],
            created_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

    def get_claim_request_detail(self, request_id: UUID) -> ClaimRequest:
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        return self.claim_request

    def update_request_attachments(
        self,
        request_id: UUID,
        attachments: list[dict],
    ) -> ClaimRequest:
        if request_id != REQUEST_ID:
            raise ValueError("ClaimRequest not found")
        self.claim_request = self.claim_request.model_copy(
            update={
                "attachments": [
                    ClaimAttachmentMetadata.model_validate(item)
                    for item in attachments
                ]
            }
        )
        return self.claim_request


class FakeClaimAttachmentStorageService:
    def save_attachment(
        self,
        *,
        file_name: str,
        content_type: str | None,
        content,
    ) -> ClaimAttachmentMetadata:
        body = content.read()
        return ClaimAttachmentMetadata(
            file_name=file_name,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(body),
            file_url="/claims/attachments/storage-key",
            metadata={"storage_key": "storage-key"},
        )


class FakeClaimAttachmentProcessingService:
    def __init__(self) -> None:
        self.processed_request_ids: list[UUID] = []

    def process_request_attachments(self, request_id: UUID) -> ClaimRequest | None:
        self.processed_request_ids.append(request_id)
        return None


class FakeEvidenceRefreshWorkflow:
    def __init__(self) -> None:
        self.request_ids: list[UUID] = []

    def run(self, request_id: UUID):
        self.request_ids.append(request_id)
        return SimpleNamespace(status="completed")


class FakeInboundEmailService:
    def __init__(self, existing_emails: list[EmailMessage]) -> None:
        self.saved: list[EmailMessage] = list(existing_emails)

    def get_case_email_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> EmailMessage | None:
        for email in self.saved:
            if email.provider_message_id == provider_message_id:
                return email
        return None

    def record_inbound_case_email(
        self,
        *,
        request_id: UUID,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        provider_message_id: str,
        email_id: UUID | None = None,
    ) -> EmailMessage:
        existing = self.get_case_email_by_provider_message_id(provider_message_id)
        if existing is not None:
            return existing
        email = EmailMessage(
            id=email_id or uuid4(),
            case_id=request_id,
            request_id=request_id,
            direction="INBOUND",
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            status="RECEIVED",
            provider_message_id=provider_message_id,
        )
        self.saved.append(email)
        return email
