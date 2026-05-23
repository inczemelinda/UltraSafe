"""Contract case-context models.

Contract contexts are retained for legacy/demo contract drafting and for the
future post-signing contract lifecycle. Quote generation is the active
pre-contract workflow.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import BaseCaseContext, CaseMetadata
from underwright.domain.models import ContractContextSource, Template


class ContractCaseMetadata(CaseMetadata):
    """Metadata defaults for the Underwright contract drafting workflow."""

    domain: Literal["contracts"] = "contracts"
    workflow_name: Literal["contract_drafting"] = "contract_drafting"


class ContractSourceInputs(BaseModel):
    """Inputs that can start or parameterize contract drafting."""

    contract_id: UUID | None = None
    client_id: int | str | None = None
    insured_asset_id: int | str | None = None
    template_id: int | str | None = None
    language: str | None = None
    generation_mode: str | None = None
    effective_date: date | str | None = None
    user_entered_overrides: dict[str, Any] = Field(default_factory=dict)


class ContractReferenceData(BaseModel):
    """Reference data loaded before contract payload or draft generation."""

    contract_source: ContractContextSource | dict[str, Any] | None = None
    client_profile: dict[str, Any] = Field(default_factory=dict)
    property_profile: dict[str, Any] = Field(default_factory=dict)
    contract_template: Template | dict[str, Any] | None = None
    policy_rules: dict[str, Any] = Field(default_factory=dict)
    external_reference_data: dict[str, Any] = Field(default_factory=dict)


class ContractDomainPayload(BaseModel):
    """Contract-specific payloads consumed by drafting modules."""

    contract_generation_payload: dict[str, Any] = Field(default_factory=dict)


class ContractDraftOutput(BaseModel):
    """Drafting output written by the contract drafting module."""

    draft_contract: str | None = None
    rendered_template_text: str | None = None
    final_document_text: str | None = None
    template_used: dict[str, Any] = Field(default_factory=dict)
    template_version: str | None = None
    mapped_input_fields: dict[str, Any] = Field(default_factory=dict)
    unmapped_or_missing_fields: list[str] = Field(default_factory=list)
    generation_rationale: str | None = None
    llm_drafting_summary: str | None = None
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    generated_document_reference: dict[str, Any] = Field(default_factory=dict)


class ContractGeneratedOutputs(BaseModel):
    """Generated artifacts produced during contract drafting."""

    contract_draft: ContractDraftOutput = Field(default_factory=ContractDraftOutput)


class ContractChecksAndWarnings(BaseModel):
    """Validation and mapping warnings for a contract case."""

    contract_warnings: list[str] = Field(default_factory=list)
    missing_template_fields: list[str] = Field(default_factory=list)
    unmapped_payload_fields: list[str] = Field(default_factory=list)
    inconsistent_input_values: list[str] = Field(default_factory=list)
    generation_warnings: list[str] = Field(default_factory=list)


class ContractGuidance(BaseModel):
    """Human-facing guidance that is not generated document output."""

    contract_guidance: dict[str, Any] = Field(default_factory=dict)


class ContractExternalSignals(BaseModel):
    """External signals reserved for future enrichment of contract cases."""

    location_signals: dict[str, Any] = Field(default_factory=dict)
    property_signals: dict[str, Any] = Field(default_factory=dict)
    regulatory_signals: dict[str, Any] = Field(default_factory=dict)


class ContractReviewState(BaseModel):
    """Review-screen state derived from the contract case context."""

    contract_review_view: Any | None = None
    available_actions: list[str] = Field(default_factory=list)


class ContractCaseContext(BaseCaseContext):
    """Concrete Underwright case context for contract drafting."""

    case_metadata: ContractCaseMetadata = Field(default_factory=ContractCaseMetadata)
    source_inputs: ContractSourceInputs = Field(default_factory=ContractSourceInputs)
    reference_data: ContractReferenceData = Field(default_factory=ContractReferenceData)
    domain_payload: ContractDomainPayload = Field(default_factory=ContractDomainPayload)
    generated_outputs: ContractGeneratedOutputs = Field(
        default_factory=ContractGeneratedOutputs
    )
    checks_and_warnings: ContractChecksAndWarnings = Field(
        default_factory=ContractChecksAndWarnings
    )
    guidance: ContractGuidance = Field(default_factory=ContractGuidance)
    external_signals: ContractExternalSignals = Field(
        default_factory=ContractExternalSignals
    )
    review_state: ContractReviewState = Field(default_factory=ContractReviewState)


__all__ = [
    "ContractCaseContext",
    "ContractCaseMetadata",
    "ContractChecksAndWarnings",
    "ContractDomainPayload",
    "ContractDraftOutput",
    "ContractExternalSignals",
    "ContractGeneratedOutputs",
    "ContractGuidance",
    "ContractReferenceData",
    "ContractReviewState",
    "ContractSourceInputs",
]
