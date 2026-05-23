from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import _utc_now


class QuoteDocument(BaseModel):
    """Unsigned generated quote document tied to a quote request.

    A quote document can later become the source for a contract after signing,
    but it is not itself a contract.
    """

    id: int | None = None
    quote_request_id: UUID
    template_id: int
    generation_status: Literal["pending", "success", "failed"]
    rendered_text: str
    rendered_json: dict[str, Any] = Field(default_factory=dict)
    file_url: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


__all__ = ["QuoteDocument"]
