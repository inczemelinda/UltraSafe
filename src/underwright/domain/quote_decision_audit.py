from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import _utc_now


class QuoteDecisionAuditCreate(BaseModel):
    quote_request_id: UUID
    previous_status: str
    decision_status: str
    reason: str | None = None
    decided_by_auth_user_id: int | None = None
    decided_by_name: str | None = None
    decided_by_email: str | None = None
    decided_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuoteDecisionAuditRecord(QuoteDecisionAuditCreate):
    id: int


__all__ = ["QuoteDecisionAuditCreate", "QuoteDecisionAuditRecord"]
