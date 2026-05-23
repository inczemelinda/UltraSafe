from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from underwright.application.ports import EmailProvider, EmailMessageRepository
from underwright.domain.email_message import (
    CustomerEmailMessage,
    EmailAttachment,
    EmailMessage,
)


class EmailService:
    def __init__(
        self,
        repository: EmailMessageRepository,
        provider: EmailProvider | None = None,
        from_email: str | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.from_email = from_email

    def send_case_email(
        self,
        case_id: UUID,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        request_id: UUID | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> EmailMessage:
        if self.provider is None or not self.from_email:
            raise RuntimeError("Email provider is required for sending emails")

        email = EmailMessage(
            id=uuid4(),
            case_id=case_id,
            direction="OUTBOUND",
            from_email=self.from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            status="DRAFT",
            request_id=request_id,
        )

        try:
            provider_message_id = self.provider.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                html_body=html_body,
                reply_to=reply_to,
                attachments=attachments,
            )

            email.status = "SENT"
            email.provider_message_id = provider_message_id
            email.sent_at = datetime.now(timezone.utc)

        except Exception as exc:
            email.status = "FAILED"
            email.error_message = str(exc)

        return self.repository.save(email)

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
        existing = self.repository.get_by_provider_message_id(provider_message_id)
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
            created_at=datetime.now(timezone.utc),
        )
        return self.repository.save(email)

    def get_case_email_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> EmailMessage | None:
        return self.repository.get_by_provider_message_id(provider_message_id)

    def list_case_emails(self, case_id: UUID) -> list[EmailMessage]:
        return self.repository.list_by_case_id(case_id)

    def list_customer_emails(self, customer_id: int) -> list[CustomerEmailMessage]:
        return self.repository.list_by_customer_id(customer_id)
