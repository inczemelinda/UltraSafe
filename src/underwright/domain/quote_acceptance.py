from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


QuoteAcceptanceMethod = Literal["client_portal", "employee_recorded", "seed", "api"]


class QuoteAcceptance(BaseModel):
    id: int | None = None
    quote_request_id: UUID
    quote_document_id: int
    accepted_by_auth_user_id: int | None = None
    accepted_by_customer_id: int
    signer_name: str
    signer_email: str
    signer_role: str | None = None
    accepted_at: datetime
    acceptance_method: QuoteAcceptanceMethod
    ip_address: str | None = None
    user_agent: str | None = None
    acceptance_statement: str
    quote_content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class QuoteAcceptanceCreate(BaseModel):
    quote_request_id: UUID
    quote_document_id: int
    accepted_by_auth_user_id: int | None = None
    accepted_by_customer_id: int
    signer_name: str
    signer_email: str
    signer_role: str | None = None
    acceptance_method: QuoteAcceptanceMethod
    ip_address: str | None = None
    user_agent: str | None = None
    acceptance_statement: str
    quote_content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuoteAcceptanceInput(BaseModel):
    signer_name: str
    signer_email: str
    signer_role: str | None = None
    acceptance_statement: str


__all__ = [
    "QuoteAcceptance",
    "QuoteAcceptanceCreate",
    "QuoteAcceptanceInput",
    "QuoteAcceptanceMethod",
]
