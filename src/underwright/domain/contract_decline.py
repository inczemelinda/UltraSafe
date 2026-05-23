from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ContractDecline(BaseModel):
    id: int | None = None
    contract_id: UUID
    source_quote_request_id: UUID | None = None
    declined_by_auth_user_id: int | None = None
    declined_by_customer_id: int
    reason: str | None = None
    declined_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractDeclineCreate(BaseModel):
    contract_id: UUID
    source_quote_request_id: UUID | None = None
    declined_by_auth_user_id: int | None = None
    declined_by_customer_id: int
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContractDeclineInput(BaseModel):
    reason: str | None = None


__all__ = [
    "ContractDecline",
    "ContractDeclineCreate",
    "ContractDeclineInput",
]
