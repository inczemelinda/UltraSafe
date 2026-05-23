from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from underwright.api.dependencies import (
    get_current_auth_user,
    get_current_employee_user,
    get_email_read_service,
    get_email_send_service,
)
from underwright.api.main import create_app
from underwright.domain.auth_user import AuthUser
from underwright.domain.email_message import CustomerEmailMessage, EmailMessage


CASE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CUSTOMER_ID = 1001


def test_email_routes_require_employee_role() -> None:
    app = create_app()
    app.dependency_overrides[get_email_read_service] = lambda: FakeEmailService()

    assert TestClient(app).get(f"/emails/case/{CASE_ID}").status_code == 401
    assert TestClient(app).get(f"/emails/customer/{CUSTOMER_ID}").status_code == 401

    app.dependency_overrides[get_current_auth_user] = lambda: _client_user()
    assert TestClient(app).get(f"/emails/case/{CASE_ID}").status_code == 403
    assert TestClient(app).get(f"/emails/customer/{CUSTOMER_ID}").status_code == 403


def test_employee_can_send_case_email() -> None:
    app = create_app()
    service = FakeEmailService()
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_send_service] = lambda: service

    response = TestClient(app).post(
        "/emails/send",
        json={
            "case_id": str(CASE_ID),
            "to_email": "client@example.com",
            "subject": "Evidence request",
            "body": "Please send evidence.",
        },
    )

    assert response.status_code == 200
    assert service.sent == [
        {
            "case_id": CASE_ID,
            "to_email": "client@example.com",
            "subject": "Evidence request",
            "body": "Please send evidence.",
        }
    ]
    assert response.json()["status"] == "SENT"


def test_employee_can_list_case_emails() -> None:
    app = create_app()
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_read_service] = lambda: FakeEmailService()

    response = TestClient(app).get(f"/emails/case/{CASE_ID}")

    assert response.status_code == 200
    assert response.json()[0]["case_id"] == str(CASE_ID)


def test_employee_can_list_customer_email_history() -> None:
    app = create_app()
    service = FakeEmailService()
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_read_service] = lambda: service

    response = TestClient(app).get(f"/emails/customer/{CUSTOMER_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert service.customer_ids == [CUSTOMER_ID]
    assert [item["subject"] for item in payload] == [
        "Latest evidence request",
        "Earlier coverage update",
    ]
    assert payload[0]["customer_id"] == CUSTOMER_ID
    assert payload[0]["case_reference"] == "Claim bbbbbbbb"
    assert payload[0]["body_preview"] == "Latest request preview."
    assert payload[0]["body_text"] == "Latest request full body."
    assert payload[0]["direction"] == "OUTBOUND"


def test_customer_email_history_returns_truncated_preview_and_full_body() -> None:
    app = create_app()
    full_body = (
        "Hello Alex,\n\n"
        "Decision: Denied\n\n"
        "Decision justification:\nThis is not a good claim.\n\n"
        "Regards,\n"
        "Underwright Claims Team"
    )
    service = FakeEmailService(
        customer_emails=[
            _customer_email(
                customer_id=CUSTOMER_ID,
                subject="Your Underwright claim decision",
                body_preview="Hello Alex,\n\nDecision: Denied\n\nRegards,\nUn",
                body_text=full_body,
            )
        ]
    )
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_read_service] = lambda: service

    response = TestClient(app).get(f"/emails/customer/{CUSTOMER_ID}")

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["body_preview"].endswith("Un")
    assert payload["body_text"].endswith("Underwright Claims Team")
    assert "This is not a good claim." in payload["body_text"]


def test_employee_customer_email_history_empty_state() -> None:
    app = create_app()
    service = FakeEmailService(customer_emails=[])
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_read_service] = lambda: service

    response = TestClient(app).get(f"/emails/customer/{CUSTOMER_ID}")

    assert response.status_code == 200
    assert response.json() == []
    assert service.customer_ids == [CUSTOMER_ID]


def test_read_email_routes_do_not_require_outbound_email_config(monkeypatch) -> None:
    for name in [
        "POSTMARK_SERVER_TOKEN",
        "EMAIL_SMTP_HOST",
        "EMAIL_USERNAME",
        "EMAIL_PASSWORD",
        "EMAIL_FROM",
    ]:
        monkeypatch.delenv(name, raising=False)

    app = create_app()
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()
    app.dependency_overrides[get_email_read_service] = lambda: FakeEmailService()

    client = TestClient(app)
    assert client.get(f"/emails/case/{CASE_ID}").status_code == 200
    assert client.get(f"/emails/customer/{CUSTOMER_ID}").status_code == 200


def test_send_email_route_still_requires_outbound_email_config(monkeypatch) -> None:
    for name in [
        "POSTMARK_SERVER_TOKEN",
        "EMAIL_SMTP_HOST",
        "EMAIL_USERNAME",
        "EMAIL_PASSWORD",
        "EMAIL_FROM",
    ]:
        monkeypatch.delenv(name, raising=False)

    app = create_app()
    app.dependency_overrides[get_current_employee_user] = lambda: _employee_user()

    response = TestClient(app, raise_server_exceptions=False).post(
        "/emails/send",
        json={
            "case_id": str(CASE_ID),
            "to_email": "client@example.com",
            "subject": "Evidence request",
            "body": "Please send evidence.",
        },
    )

    assert response.status_code == 500


class FakeEmailService:
    def __init__(
        self,
        customer_emails: list[CustomerEmailMessage] | None = None,
    ) -> None:
        self.sent: list[dict] = []
        self.customer_ids: list[int] = []
        self.customer_emails = customer_emails

    def send_case_email(
        self,
        *,
        case_id: UUID,
        to_email: str,
        subject: str,
        body: str,
    ) -> EmailMessage:
        self.sent.append(
            {
                "case_id": case_id,
                "to_email": to_email,
                "subject": subject,
                "body": body,
            }
        )
        return _email(case_id=case_id, to_email=to_email, subject=subject, body=body)

    def list_case_emails(self, case_id: UUID) -> list[EmailMessage]:
        return [_email(case_id=case_id)]

    def list_customer_emails(self, customer_id: int) -> list[CustomerEmailMessage]:
        self.customer_ids.append(customer_id)
        if self.customer_emails is not None:
            return self.customer_emails
        return [
            _customer_email(
                customer_id=customer_id,
                subject="Latest evidence request",
                body_preview="Latest request preview.",
                body_text="Latest request full body.",
                created_at=datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc),
            ),
            _customer_email(
                customer_id=customer_id,
                subject="Earlier coverage update",
                body_preview="Earlier update preview.",
                body_text="Earlier update full body.",
                created_at=datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            ),
        ]


def _email(
    *,
    case_id: UUID = CASE_ID,
    to_email: str = "client@example.com",
    subject: str = "Evidence request",
    body: str = "Please send evidence.",
) -> EmailMessage:
    return EmailMessage(
        id=uuid4(),
        case_id=case_id,
        direction="OUTBOUND",
        from_email="claims@example.com",
        to_email=to_email,
        subject=subject,
        body=body,
        status="SENT",
        provider_message_id="message-id",
        created_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        sent_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )


def _customer_email(
    *,
    customer_id: int = CUSTOMER_ID,
    subject: str = "Evidence request",
    body_preview: str = "Please send evidence.",
    body_text: str = "Please send evidence.",
    created_at: datetime = datetime(2026, 5, 14, tzinfo=timezone.utc),
) -> CustomerEmailMessage:
    return CustomerEmailMessage(
        id=uuid4(),
        customer_id=customer_id,
        case_id=CASE_ID,
        case_reference="Claim bbbbbbbb",
        direction="OUTBOUND",
        status="SENT",
        from_email="claims@example.com",
        to_email="client@example.com",
        subject=subject,
        body_preview=body_preview,
        body_text=body_text,
        body_html=None,
        provider="smtp",
        provider_message_id="message-id",
        created_at=created_at,
        sent_at=created_at,
    )


def _employee_user() -> AuthUser:
    return AuthUser(
        id=1,
        email="employee@example.com",
        password_hash="hash",
        role="employee",
        full_name="Employee",
    )


def _client_user() -> AuthUser:
    return AuthUser(
        id=2,
        email="client@example.com",
        password_hash="hash",
        role="client",
        full_name="Client",
        client_id=1001,
    )
