from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Literal


EmailDirection = Literal["OUTBOUND", "INBOUND"]
EmailStatus = Literal["DRAFT", "SENT", "FAILED", "RECEIVED"]


@dataclass(frozen=True)
class EmailAttachment:
    file_name: str
    content_type: str
    content: bytes


@dataclass
class EmailMessage:
    id: UUID
    direction: EmailDirection
    from_email: str
    to_email: str
    subject: str
    body: str
    status: EmailStatus
    case_id: UUID | None = None
    request_id: UUID | None = None
    provider_message_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None


@dataclass(frozen=True)
class CustomerEmailMessage:
    id: UUID
    customer_id: int
    case_id: UUID | None
    case_reference: str | None
    direction: EmailDirection
    status: EmailStatus
    to_email: str
    from_email: str
    subject: str
    body_preview: str
    body_text: str
    body_html: str | None
    provider: str | None
    provider_message_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None
    received_at: datetime | None = None
