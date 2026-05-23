from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ClaimReviewHeader(BaseModel):
    case_id: UUID | None = None
    request_id: UUID | None = None
    domain: str
    workflow_status: str


class ClaimClientPanel(BaseModel):
    client_id: int | str | UUID | None = None
    client_data: dict[str, Any] = Field(default_factory=dict)


class ClaimDetailPanel(BaseModel):
    claim_data: dict[str, Any] = Field(default_factory=dict)


class ClaimAttachmentsPanel(BaseModel):
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ClaimReviewView(BaseModel):
    header: ClaimReviewHeader
    client_panel: ClaimClientPanel
    claim_detail_panel: ClaimDetailPanel
    attachments_panel: ClaimAttachmentsPanel
    ai_validation_panel: dict[str, Any] = Field(default_factory=dict)
    classification_panel: dict[str, Any] = Field(default_factory=dict)
    summary_panel: dict[str, Any] = Field(default_factory=dict)
    coverage_precheck: dict[str, Any] | None = None
    coverage_assessment: dict[str, Any] | None = None
    document_consistency: dict[str, Any] = Field(default_factory=dict)
    supporting_facts: list[dict[str, Any]] = Field(default_factory=list)
    discrepancies: list[dict[str, Any]] = Field(default_factory=list)
    extracted_documents: dict[str, Any] = Field(default_factory=dict)
    required_evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = Field(default_factory=list)
    suggested_next_action: str | None = None
    human_readable_summary: str | None = None
    evidence_request_draft: dict[str, Any] | None = None
    confidence_panel: dict[str, Any] = Field(default_factory=dict)
    warnings_panel: dict[str, Any] = Field(default_factory=dict)
    available_actions: list[str] = Field(default_factory=list)


__all__ = [
    "ClaimAttachmentsPanel",
    "ClaimClientPanel",
    "ClaimDetailPanel",
    "ClaimReviewHeader",
    "ClaimReviewView",
]
