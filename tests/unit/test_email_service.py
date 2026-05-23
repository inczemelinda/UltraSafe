from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from underwright.api.dependencies import get_email_read_service, get_email_send_service
from underwright.application.services.email_service import EmailService
from underwright.domain.email_message import (
    CustomerEmailMessage,
    EmailAttachment,
    EmailMessage,
)


CASE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_CASE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def test_email_service_sends_and_persists_sent_message() -> None:
    provider = FakeEmailProvider("provider-message-id")
    repository = FakeEmailRepository()
    service = EmailService(
        provider=provider,
        repository=repository,
        from_email="claims@example.com",
    )

    email = service.send_case_email(
        case_id=CASE_ID,
        to_email="client@example.com",
        subject="Evidence request",
        body="Please send evidence.",
    )

    assert provider.sent_messages == [
        {
            "to_email": "client@example.com",
            "subject": "Evidence request",
            "body": "Please send evidence.",
            "html_body": None,
        }
    ]
    assert email.status == "SENT"
    assert email.provider_message_id == "provider-message-id"
    assert email.sent_at is not None
    assert repository.saved == [email]


def test_email_service_persists_failed_delivery() -> None:
    service = EmailService(
        provider=FakeEmailProvider(error=RuntimeError("SMTP failed")),
        repository=FakeEmailRepository(),
        from_email="claims@example.com",
    )

    email = service.send_case_email(
        case_id=CASE_ID,
        to_email="client@example.com",
        subject="Evidence request",
        body="Please send evidence.",
    )

    assert email.status == "FAILED"
    assert email.error_message == "SMTP failed"
    assert email.provider_message_id is None


def test_email_service_forwards_html_body_to_provider() -> None:
    provider = FakeEmailProvider("provider-message-id")
    service = EmailService(
        provider=provider,
        repository=FakeEmailRepository(),
        from_email="claims@example.com",
    )

    service.send_case_email(
        case_id=CASE_ID,
        to_email="client@example.com",
        subject="Claim decision",
        body="Decision: Approved",
        html_body="<p><strong>Decision:</strong> Approved</p>",
    )

    assert provider.sent_messages == [
        {
            "to_email": "client@example.com",
            "subject": "Claim decision",
            "body": "Decision: Approved",
            "html_body": "<p><strong>Decision:</strong> Approved</p>",
        }
    ]


def test_email_service_forwards_reply_to_and_attachments_to_provider() -> None:
    provider = FakeEmailProvider("provider-message-id")
    attachment = EmailAttachment(
        file_name="evidence.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.4\n%%EOF\n",
    )
    service = EmailService(
        provider=provider,
        repository=FakeEmailRepository(),
        from_email="claims@example.com",
    )

    service.send_case_email(
        case_id=CASE_ID,
        to_email="client@example.com",
        subject="Evidence request",
        body="Please send evidence.",
        reply_to="claims+reply-token@inbound.postmarkapp.com",
        attachments=[attachment],
    )

    assert provider.sent_messages == [
        {
            "to_email": "client@example.com",
            "subject": "Evidence request",
            "body": "Please send evidence.",
            "html_body": None,
            "reply_to": "claims+reply-token@inbound.postmarkapp.com",
            "attachments": [attachment],
        }
    ]


def test_email_dependency_uses_postmark_server_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "postmark-token")
    monkeypatch.setenv("EMAIL_FROM", "claims@example.com")

    service = get_email_send_service()

    assert service.provider.host == "smtp.postmarkapp.com"
    assert service.provider.username == "postmark-token"
    assert service.provider.password == "postmark-token"
    assert service.from_email == "claims@example.com"


def test_email_read_dependency_does_not_require_outbound_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in [
        "POSTMARK_SERVER_TOKEN",
        "EMAIL_SMTP_HOST",
        "EMAIL_USERNAME",
        "EMAIL_PASSWORD",
        "EMAIL_FROM",
    ]:
        monkeypatch.delenv(name, raising=False)

    service = get_email_read_service()

    assert service.provider is None
    assert service.from_email is None


def test_send_case_email_requires_provider_for_read_only_service() -> None:
    service = EmailService(repository=FakeEmailRepository())

    with pytest.raises(RuntimeError, match="Email provider is required"):
        service.send_case_email(
            case_id=CASE_ID,
            to_email="client@example.com",
            subject="Evidence request",
            body="Please send evidence.",
        )


def test_email_service_lists_customer_emails_newest_first_and_isolated() -> None:
    repository = FakeEmailRepository(
        customer_emails=[
            _customer_email(
                customer_id=1001,
                subject="Older",
                created_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
            ),
            _customer_email(
                customer_id=1002,
                subject="Other customer",
                case_id=OTHER_CASE_ID,
                created_at=datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
            ),
            _customer_email(
                customer_id=1001,
                subject="Newer",
                created_at=datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    service = EmailService(
        provider=FakeEmailProvider(),
        repository=repository,
        from_email="claims@example.com",
    )

    emails = service.list_customer_emails(1001)

    assert [email.subject for email in emails] == ["Newer", "Older"]
    assert all(email.customer_id == 1001 for email in emails)


def test_email_service_records_inbound_case_email_once_by_provider_message_id() -> None:
    repository = FakeEmailRepository()
    service = EmailService(repository=repository)

    first = service.record_inbound_case_email(
        request_id=CASE_ID,
        from_email="client@example.com",
        to_email="claims@example.com",
        subject="Re: Evidence request",
        body="Attached.",
        provider_message_id="postmark-message-id",
    )
    duplicate = service.record_inbound_case_email(
        request_id=CASE_ID,
        from_email="client@example.com",
        to_email="claims@example.com",
        subject="Re: Evidence request",
        body="Attached again.",
        provider_message_id="postmark-message-id",
    )

    assert first is duplicate
    assert len(repository.saved) == 1
    assert first.direction == "INBOUND"
    assert first.status == "RECEIVED"
    assert first.request_id == CASE_ID


class FakeEmailProvider:
    def __init__(
        self,
        message_id: str = "message-id",
        *,
        error: Exception | None = None,
    ) -> None:
        self.message_id = message_id
        self.error = error
        self.sent_messages: list[dict[str, object]] = []

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> str:
        if self.error is not None:
            raise self.error
        message = {
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "html_body": html_body,
        }
        if reply_to:
            message["reply_to"] = reply_to
        if attachments is not None:
            message["attachments"] = attachments
        self.sent_messages.append(message)
        return self.message_id


class FakeEmailRepository:
    def __init__(
        self,
        customer_emails: list[CustomerEmailMessage] | None = None,
    ) -> None:
        self.saved: list[EmailMessage] = []
        self.customer_emails = customer_emails or []

    def save(self, email: EmailMessage) -> EmailMessage:
        self.saved.append(email)
        return email

    def list_by_case_id(self, case_id: UUID) -> list[EmailMessage]:
        return [email for email in self.saved if email.case_id == case_id]

    def list_by_customer_id(self, customer_id: int) -> list[CustomerEmailMessage]:
        return sorted(
            (
                email
                for email in self.customer_emails
                if email.customer_id == customer_id
            ),
            key=lambda email: email.created_at
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def get_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> EmailMessage | None:
        for email in self.saved:
            if email.provider_message_id == provider_message_id:
                return email
        return None


def _customer_email(
    *,
    customer_id: int,
    subject: str,
    created_at: datetime,
    case_id: UUID = CASE_ID,
) -> CustomerEmailMessage:
    return CustomerEmailMessage(
        id=case_id,
        customer_id=customer_id,
        case_id=case_id,
        case_reference=f"Claim {str(case_id)[:8]}",
        direction="OUTBOUND",
        status="SENT",
        from_email="claims@example.com",
        to_email="client@example.com",
        subject=subject,
        body_preview=f"{subject} preview",
        body_text=f"{subject} full body",
        body_html=None,
        provider="smtp",
        provider_message_id=f"{subject}-message",
        created_at=created_at,
        sent_at=created_at,
    )
