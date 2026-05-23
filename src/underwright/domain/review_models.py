from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewHeader(BaseModel):
    """Header data for a review screen."""

    # Workflow instance id.
    case_id: UUID | None = None
    # Contract id from the persisted contract row.
    contract_id: UUID | None = None
    domain: str
    workflow_status: str


class SourceInputPanel(BaseModel):
    """Source-input summary for contract review."""

    # Contract id shown to consumers.
    contract_id: UUID | None = None
    customer_summary: dict[str, Any] | None = None
    insured_asset_summary: dict[str, Any] | None = None


class GeneratedOutputPanel(BaseModel):
    """Generated output summary for contract review."""

    draft_contract_text: str | None = None
    generated_document_reference: dict[str, Any] | None = None
    status: str | None = None


class TemplatePanel(BaseModel):
    """Template metadata for contract review."""

    template_id: int | None = None
    template_code: str | None = None
    template_name: str | None = None
    template_version: str | None = None


class WarningsPanel(BaseModel):
    """Lightweight warnings for missing review data."""

    missing_fields: list[str] = Field(default_factory=list)
    unmapped_fields: list[str] = Field(default_factory=list)


class RationalePanel(BaseModel):
    """Generation rationale for contract review."""

    payload_sections_used: list[str] = Field(default_factory=list)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)


class AuditSummaryItem(BaseModel):
    """Compact audit row for the review screen."""

    timestamp: str | None = None
    event_type: str
    module_or_service: str | None = None
    summary: str | None = None


class GuidancePanel(BaseModel):
    """Human-facing guidance for the underwriter review screen (can be empty)."""

    guidance_items: list[str] = Field(default_factory=list)
    guidance_metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalSignalsPanel(BaseModel):
    """External enrichment signals for contract review (can be empty)."""

    location_signals: dict[str, Any] = Field(default_factory=dict)
    property_signals: dict[str, Any] = Field(default_factory=dict)
    regulatory_signals: dict[str, Any] = Field(default_factory=dict)


class ContractReviewView(BaseModel):
    """UI-ready read model for reviewing a contract draft."""

    header: ReviewHeader
    source_input_panel: SourceInputPanel
    generated_output_panel: GeneratedOutputPanel
    template_panel: TemplatePanel
    warnings_panel: WarningsPanel = Field(default_factory=WarningsPanel)
    rationale_panel: RationalePanel = Field(default_factory=RationalePanel)
    guidance_panel: GuidancePanel = Field(default_factory=GuidancePanel)
    external_signals_panel: ExternalSignalsPanel = Field(default_factory=ExternalSignalsPanel)
    audit_summary: list[AuditSummaryItem] = Field(default_factory=list)
    available_user_actions: list[str] = Field(default_factory=list)


__all__ = [
    "AuditSummaryItem",
    "ContractReviewView",
    "ExternalSignalsPanel",
    "GeneratedOutputPanel",
    "GuidancePanel",
    "RationalePanel",
    "ReviewHeader",
    "SourceInputPanel",
    "TemplatePanel",
    "WarningsPanel",
]
