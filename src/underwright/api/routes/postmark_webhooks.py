from __future__ import annotations

import base64
import binascii
import os
import re
import secrets
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field

from underwright.api.dependencies import (
    get_case_context_service,
    get_claim_attachment_processing_service,
    get_claim_attachment_storage_service,
    get_claim_request_service,
    get_email_read_service,
    get_evidence_refresh_workflow,
)
from underwright.application.services.case_context_service import CaseContextService
from underwright.application.services.claim_attachment_processing_service import (
    ClaimAttachmentProcessingService,
)
from underwright.application.services.claim_attachment_storage_service import (
    ClaimAttachmentStorageService,
    ClaimAttachmentTooLargeError,
    EmptyClaimAttachmentError,
    UnsupportedClaimAttachmentContentTypeError,
)
from underwright.application.services.claim_request_service import ClaimRequestService
from underwright.application.services.email_service import EmailService
from underwright.application.workflows.evidence_refresh_workflow import (
    EvidenceRefreshWorkflow,
)
from underwright.domain.claim_case_context import ClaimCaseContext
from underwright.domain.claim_request import ClaimAttachmentMetadata, ClaimRequest


router = APIRouter(prefix="/webhooks/postmark", tags=["postmark-webhooks"])
_security = HTTPBasic(auto_error=False)
_SUBJECT_TOKEN_PATTERN = re.compile(r"\[UW-CLAIM:([A-Za-z0-9_-]+)\]")


class PostmarkAddress(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(default="", alias="Email")
    mailbox_hash: str = Field(default="", alias="MailboxHash")


class PostmarkAttachment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    content: str = Field(alias="Content")
    content_type: str | None = Field(default=None, alias="ContentType")


class PostmarkInboundPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="MessageID")
    from_email: str | None = Field(default=None, alias="From")
    from_full: PostmarkAddress | None = Field(default=None, alias="FromFull")
    to_email: str | None = Field(default=None, alias="To")
    to_full: list[PostmarkAddress] = Field(default_factory=list, alias="ToFull")
    mailbox_hash: str | None = Field(default=None, alias="MailboxHash")
    subject: str | None = Field(default=None, alias="Subject")
    text_body: str | None = Field(default=None, alias="TextBody")
    html_body: str | None = Field(default=None, alias="HtmlBody")
    stripped_text_reply: str | None = Field(default=None, alias="StrippedTextReply")
    attachments: list[PostmarkAttachment] = Field(
        default_factory=list,
        alias="Attachments",
    )


class PostmarkInboundResponse(BaseModel):
    status: str
    message: str
    request_id: UUID | None = None
    email_message_id: UUID | None = None
    attachment_count: int = 0
    skipped_attachment_count: int = 0
    refresh_status: str | None = None
    duplicate: bool = False


def _require_postmark_webhook_auth(
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> bool:
    expected_username = os.environ.get("POSTMARK_WEBHOOK_USERNAME")
    expected_password = os.environ.get("POSTMARK_WEBHOOK_PASSWORD")
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Postmark webhook credentials are not configured"},
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Postmark webhook authentication required"},
            headers={"WWW-Authenticate": "Basic"},
        )
    username_ok = secrets.compare_digest(credentials.username, expected_username)
    password_ok = secrets.compare_digest(credentials.password, expected_password)
    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Invalid Postmark webhook credentials"},
        )
    return True


@router.post("/inbound", response_model=PostmarkInboundResponse)
def receive_postmark_inbound_email(
    payload: PostmarkInboundPayload,
    _authorized: bool = Depends(_require_postmark_webhook_auth),
    case_context_service: CaseContextService = Depends(get_case_context_service),
    claim_service: ClaimRequestService = Depends(get_claim_request_service),
    storage_service: ClaimAttachmentStorageService = Depends(
        get_claim_attachment_storage_service
    ),
    processing_service: ClaimAttachmentProcessingService = Depends(
        get_claim_attachment_processing_service
    ),
    refresh_workflow: EvidenceRefreshWorkflow = Depends(get_evidence_refresh_workflow),
    email_service: EmailService = Depends(get_email_read_service),
) -> PostmarkInboundResponse:
    provider_message_id = payload.message_id.strip()
    existing_email = email_service.get_case_email_by_provider_message_id(
        provider_message_id
    )
    if existing_email is not None:
        return PostmarkInboundResponse(
            status="duplicate",
            message="Inbound email was already processed.",
            request_id=existing_email.request_id or existing_email.case_id,
            email_message_id=existing_email.id,
            duplicate=True,
        )

    reply_token = _extract_reply_token(payload)
    if not reply_token:
        return PostmarkInboundResponse(
            status="ignored",
            message="Inbound email did not include a claim reply token.",
        )

    try:
        case_context = (
            case_context_service.get_latest_claim_case_context_by_evidence_reply_token(
                reply_token
            )
        )
    except ValueError:
        return PostmarkInboundResponse(
            status="ignored",
            message="Inbound email reply token did not match a claim.",
        )

    request_id = UUID(str(case_context.source_inputs.request_id))
    claim = claim_service.get_claim_request_detail(request_id)
    if _claim_has_provider_message_id(claim, provider_message_id):
        email = email_service.record_inbound_case_email(
            request_id=request_id,
            from_email=_sender_email(payload),
            to_email=_recipient_email(payload),
            subject=_subject(payload),
            body=_body(payload),
            provider_message_id=provider_message_id,
        )
        return PostmarkInboundResponse(
            status="duplicate",
            message="Inbound email attachments were already present on the claim.",
            request_id=request_id,
            email_message_id=email.id,
            duplicate=True,
        )

    email_id = uuid4()
    received_at = datetime.now(timezone.utc).isoformat()
    stored_attachments, skipped_attachment_count = _store_postmark_attachments(
        payload,
        request_id=request_id,
        email_id=email_id,
        reply_token=reply_token,
        case_context=case_context,
        provider_message_id=provider_message_id,
        received_at=received_at,
        storage_service=storage_service,
    )
    if stored_attachments:
        _append_claim_attachments(
            request_id,
            claim,
            stored_attachments,
            claim_service,
        )
        try:
            processing_service.process_request_attachments(request_id)
        except Exception:
            # The email has arrived and attachments are durable; refresh can be
            # retried manually without asking Postmark to redeliver the webhook.
            pass

    email = email_service.record_inbound_case_email(
        request_id=request_id,
        from_email=_sender_email(payload),
        to_email=_recipient_email(payload),
        subject=_subject(payload),
        body=_body(payload),
        provider_message_id=provider_message_id,
        email_id=email_id,
    )

    refresh_status = "pending"
    try:
        refresh_result = refresh_workflow.run(request_id)
        refresh_status = refresh_result.status
    except Exception:
        refresh_status = "pending"

    return PostmarkInboundResponse(
        status="processed",
        message="Inbound claim email was processed.",
        request_id=request_id,
        email_message_id=email.id,
        attachment_count=len(stored_attachments),
        skipped_attachment_count=skipped_attachment_count,
        refresh_status=refresh_status,
    )


def _extract_reply_token(payload: PostmarkInboundPayload) -> str:
    candidates = [
        payload.mailbox_hash,
        *(address.mailbox_hash for address in payload.to_full),
    ]
    for candidate in candidates:
        token = _normalize_reply_token(candidate)
        if token:
            return token

    match = _SUBJECT_TOKEN_PATTERN.search(payload.subject or "")
    return _normalize_reply_token(match.group(1) if match else "")


def _normalize_reply_token(value: str | None) -> str:
    return str(value or "").strip().lower()


def _store_postmark_attachments(
    payload: PostmarkInboundPayload,
    *,
    request_id: UUID,
    email_id: UUID,
    reply_token: str,
    case_context: ClaimCaseContext,
    provider_message_id: str,
    received_at: str,
    storage_service: ClaimAttachmentStorageService,
) -> tuple[list[ClaimAttachmentMetadata], int]:
    stored_attachments: list[ClaimAttachmentMetadata] = []
    skipped_attachment_count = 0
    for attachment in payload.attachments:
        try:
            content = base64.b64decode(attachment.content, validate=True)
            stored = storage_service.save_attachment(
                file_name=attachment.name,
                content_type=attachment.content_type,
                content=BytesIO(content),
            )
        except (
            binascii.Error,
            ClaimAttachmentTooLargeError,
            EmptyClaimAttachmentError,
            UnsupportedClaimAttachmentContentTypeError,
        ):
            skipped_attachment_count += 1
            continue

        stored_attachments.append(
            _claim_email_attachment_metadata(
                request_id,
                stored,
                email_id=email_id,
                reply_token=reply_token,
                case_context=case_context,
                payload=payload,
                provider_message_id=provider_message_id,
                received_at=received_at,
            )
        )
    return stored_attachments, skipped_attachment_count


def _claim_email_attachment_metadata(
    request_id: UUID,
    stored: ClaimAttachmentMetadata,
    *,
    email_id: UUID,
    reply_token: str,
    case_context: ClaimCaseContext,
    payload: PostmarkInboundPayload,
    provider_message_id: str,
    received_at: str,
) -> ClaimAttachmentMetadata:
    attachment_id = uuid4()
    draft = case_context.generated_outputs.evidence_request_draft
    metadata = dict(stored.metadata or {})
    metadata.update(
        {
            "attachment_id": str(attachment_id),
            "claim_id": str(request_id),
            "source": "email_hook",
            "status": "uploaded",
            "sender_email": _sender_email(payload),
            "received_at": received_at,
            "subject": _subject(payload),
            "provider_message_id": provider_message_id,
            "email_message_id": str(email_id),
            "reply_token": reply_token,
            "evidence_request_id": str(draft.draft_id) if draft is not None else None,
        }
    )
    return ClaimAttachmentMetadata(
        file_name=stored.file_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        file_url=f"/claims/{request_id}/attachments/{attachment_id}",
        metadata=metadata,
    )


def _append_claim_attachments(
    request_id: UUID,
    claim: ClaimRequest,
    new_attachments: list[ClaimAttachmentMetadata],
    claim_service: ClaimRequestService,
) -> ClaimRequest:
    attachments = [
        attachment.model_dump(mode="json")
        for attachment in claim.attachments
    ]
    attachments.extend(
        attachment.model_dump(mode="json")
        for attachment in new_attachments
    )
    return claim_service.update_request_attachments(request_id, attachments)


def _claim_has_provider_message_id(
    claim: ClaimRequest,
    provider_message_id: str,
) -> bool:
    return any(
        str(attachment.metadata.get("provider_message_id") or "")
        == provider_message_id
        for attachment in claim.attachments
    )


def _sender_email(payload: PostmarkInboundPayload) -> str:
    if payload.from_full and payload.from_full.email:
        return payload.from_full.email
    return payload.from_email or "unknown-sender"


def _recipient_email(payload: PostmarkInboundPayload) -> str:
    for address in payload.to_full:
        if address.email:
            return address.email
    return payload.to_email or "claims@underwright.local"


def _subject(payload: PostmarkInboundPayload) -> str:
    return payload.subject or "Inbound claim reply"


def _body(payload: PostmarkInboundPayload) -> str:
    return (
        payload.stripped_text_reply
        or payload.text_body
        or payload.html_body
        or ""
    )


__all__ = ["router"]
