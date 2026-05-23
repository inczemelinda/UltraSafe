"""Shared workflow state envelope for Underwright case flows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEntry(BaseModel):
    """Lightweight workflow audit entry; keep metadata safe and small."""

    timestamp: datetime = Field(default_factory=_utc_now)
    event_type: str
    module_or_service: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseMetadata(BaseModel):
    """Domain-neutral metadata that identifies one workflow run."""

    case_id: UUID | None = None
    domain: str | None = None
    workflow_name: str | None = None
    status: str = "draft"
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class PersistedCaseContext(BaseModel):
    """Persisted full case context record."""

    id: int | None = None
    case_id: UUID
    domain: str
    workflow_name: str
    status: str
    context_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class BaseCaseContext(BaseModel):
    """Generic Underwright workflow envelope.

    Leaf contexts specialize the section types. The base stays permissive so
    each case family can reuse the same lifecycle shape without inheriting
    another workflow's fields.
    """

    case_metadata: CaseMetadata = Field(default_factory=CaseMetadata)
    source_inputs: dict[str, Any] = Field(default_factory=dict)
    reference_data: dict[str, Any] = Field(default_factory=dict)
    domain_payload: dict[str, Any] = Field(default_factory=dict)
    generated_outputs: dict[str, Any] = Field(default_factory=dict)
    checks_and_warnings: dict[str, Any] = Field(default_factory=dict)
    guidance: dict[str, Any] = Field(default_factory=dict)
    external_signals: dict[str, Any] = Field(default_factory=dict)
    review_state: dict[str, Any] = Field(default_factory=dict)
    audit_trail: list[AuditEntry] = Field(default_factory=list)


__all__ = [
    "AuditEntry",
    "BaseCaseContext",
    "CaseMetadata",
    "PersistedCaseContext",
    "_utc_now",
]
