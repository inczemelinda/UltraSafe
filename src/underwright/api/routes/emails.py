from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from underwright.api.dependencies import (
    get_current_employee_user,
    get_email_read_service,
    get_email_send_service,
)
from underwright.application.services.email_service import EmailService
from underwright.domain.auth_user import AuthUser
from underwright.domain.email_message import CustomerEmailMessage


router = APIRouter(prefix="/emails", tags=["emails"])


class SendCaseEmailRequest(BaseModel):
    case_id: UUID
    to_email: EmailStr
    subject: str
    body: str


@router.post("/send")
def send_case_email(
    request: SendCaseEmailRequest,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: EmailService = Depends(get_email_send_service),
):
    email = service.send_case_email(
        case_id=request.case_id,
        to_email=request.to_email,
        subject=request.subject,
        body=request.body,
    )

    return {
        "id": str(email.id),
        "case_id": str(email.case_id) if email.case_id else None,
        "direction": email.direction,
        "from_email": email.from_email,
        "to_email": email.to_email,
        "subject": email.subject,
        "body": email.body,
        "status": email.status,
        "provider_message_id": email.provider_message_id,
        "error_message": email.error_message,
        "created_at": email.created_at,
        "sent_at": email.sent_at,
    }


@router.get("/case/{case_id}")
def list_case_emails(
    case_id: UUID,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: EmailService = Depends(get_email_read_service),
):
    emails = service.list_case_emails(case_id)

    return [
        {
            "id": str(email.id),
            "case_id": str(email.case_id) if email.case_id else None,
            "direction": email.direction,
            "from_email": email.from_email,
            "to_email": email.to_email,
            "subject": email.subject,
            "body": email.body,
            "status": email.status,
            "provider_message_id": email.provider_message_id,
            "error_message": email.error_message,
            "created_at": email.created_at,
            "sent_at": email.sent_at,
        }
        for email in emails
    ]


@router.get("/customer/{customer_id}")
def list_customer_emails(
    customer_id: int,
    _current_user: AuthUser = Depends(get_current_employee_user),
    service: EmailService = Depends(get_email_read_service),
):
    emails = service.list_customer_emails(customer_id)

    return [_customer_email_response(email) for email in emails]


def _customer_email_response(email: CustomerEmailMessage) -> dict:
    return {
        "id": str(email.id),
        "customer_id": email.customer_id,
        "case_id": str(email.case_id) if email.case_id else None,
        "case_reference": email.case_reference,
        "direction": email.direction,
        "status": email.status,
        "to_email": email.to_email,
        "from_email": email.from_email,
        "subject": email.subject,
        "body_preview": email.body_preview,
        "body_text": email.body_text,
        "body_html": email.body_html,
        "provider": email.provider,
        "provider_message_id": email.provider_message_id,
        "error_message": email.error_message,
        "created_at": email.created_at,
        "sent_at": email.sent_at,
        "received_at": email.received_at,
    }
