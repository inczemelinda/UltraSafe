from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from underwright.domain.case_context_base import _utc_now


QuoteRequestStatus = Literal[
    "draft",
    "pricing_in_progress",
    "quote_ready",
    "auto_accepted",
    "underwriter_review",
    "approved",
    "disapproved",
    "field_review_required",
    "failed",
]


class QuoteAttachmentMetadata(BaseModel):
    file_name: str
    content_type: str
    size_bytes: int
    file_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuoteRequest(BaseModel):
    """Client quote intake request created before quote workflow processing.

    This model represents quote intake data only and should not embed a full
    case context.
    """

    request_id: UUID
    client_id: int | str | UUID
    request_status: QuoteRequestStatus = "draft"

    client_data: dict[str, Any] = Field(default_factory=dict)
    asset_data: dict[str, Any] = Field(default_factory=dict)
    quote_steps: list[dict[str, Any]] = Field(default_factory=list)
    mandatory_data_status: dict[str, Any] = Field(default_factory=dict)
    attachments: list[QuoteAttachmentMetadata] = Field(default_factory=list)
    pricing_preview: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @computed_field(return_type=dict[str, Any] | None)
    @property
    def pricing(self) -> dict[str, Any] | None:
        """Expose authoritative backend pricing without persisting a duplicate column."""

        pricing = self.pricing_preview.get("pricing")
        if not isinstance(pricing, dict):
            return None
        if pricing.get("source") != "backend":
            return None
        return pricing

    @computed_field(return_type=dict[str, Any] | None)
    @property
    def risk(self) -> dict[str, Any] | None:
        """Expose authoritative backend risk without persisting a duplicate column."""

        risk_assessment = self.pricing_preview.get("risk_assessment")
        if not isinstance(risk_assessment, dict):
            return None
        if risk_assessment.get("source") != "backend":
            return None
        return risk_assessment


__all__ = [
    "QuoteAttachmentMetadata",
    "QuoteRequest",
    "QuoteRequestStatus",
]
