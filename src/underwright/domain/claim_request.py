from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from underwright.domain.case_context_base import _utc_now

_UUID_TEXT_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


ClaimRequestStatus = Literal[
    "draft",
    "submitted",
    "screening",
    "needs_underwriter_review",
    "coverage_review_required",
    "in_review",
    "completed",
    "failed",
    "precheck_rejected",
]


class ClaimAttachmentMetadata(BaseModel):
    file_name: str
    content_type: str
    size_bytes: int
    file_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimRequest(BaseModel):
    """Persisted claim intake request created before AI review starts.

    This model represents the client-submitted intake payload and should remain
    separate from ClaimCaseContext, which represents the workflow analysis state.
    """

    # Stable request id created outside the database.
    request_id: UUID
    client_id: int | str | UUID
    request_status: ClaimRequestStatus = "draft"

    client_data: dict[str, Any] = Field(default_factory=dict)
    claim_data: dict[str, Any] = Field(default_factory=dict)
    attachments: list[ClaimAttachmentMetadata] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def populate_display_claim_id(self) -> "ClaimRequest":
        if not self.claim_data:
            return self

        display_id = _clean_claim_identifier(self.claim_data.get("display_claim_id"))
        if display_id and not _is_uuid_text(display_id):
            return self

        claim_id = _clean_claim_identifier(self.claim_data.get("claim_id"))
        next_display_id = (
            claim_id
            if claim_id and not _is_uuid_text(claim_id)
            else build_claim_display_id(
                request_id=self.request_id,
                created_at=self.created_at,
                claim_id=claim_id,
            )
        )
        self.claim_data = {**self.claim_data, "display_claim_id": next_display_id}
        return self


def build_claim_display_id(
    *,
    request_id: UUID | str,
    created_at: datetime,
    claim_id: str | None = None,
) -> str:
    year = created_at.year
    suffix_source = claim_id if claim_id and _is_uuid_text(claim_id) else str(request_id)
    return f"CLM-{year}-{_claim_display_suffix(suffix_source)}"


def _claim_display_suffix(value: str) -> str:
    last_segment = value.split("-")[-1]
    digits = re.sub(r"\D", "", last_segment)
    if digits:
        return digits[-6:].zfill(6)
    normalized = re.sub(r"[^A-Za-z0-9]", "", last_segment).upper()
    return (normalized[-6:] or "000000").rjust(6, "0")


def _is_uuid_text(value: str) -> bool:
    return bool(_UUID_TEXT_PATTERN.fullmatch(value))


def _clean_claim_identifier(value: Any) -> str:
    return str(value).strip() if value is not None else ""


__all__ = [
    "build_claim_display_id",
    "ClaimAttachmentMetadata",
    "ClaimRequest",
    "ClaimRequestStatus",
]
