"""Quote case-context models.

A quote is the active pre-contract workflow: client intake data produces an
unsigned quote document that can be auto-accepted or sent to underwriter review.
After signing, a quote can become a contract.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import BaseCaseContext, CaseMetadata
from underwright.domain.models import Template


class QuoteCaseMetadata(CaseMetadata):
    """Metadata defaults for the Underwright quote workflow."""

    domain: Literal["quotes"] = "quotes"
    workflow_name: Literal["quote_generation"] = "quote_generation"


class QuoteSourceInputs(BaseModel):
    """Inputs that can start or parameterize quote generation."""

    request_id: UUID | None = None
    client_id: int | str | UUID | None = None
    asset_id: int | str | UUID | None = None
    template_id: int | str | None = None
    language: str | None = None
    user_entered_overrides: dict[str, Any] = Field(default_factory=dict)


class QuoteReferenceData(BaseModel):
    """Reference data loaded before quote generation."""

    quote_request: dict[str, Any] = Field(default_factory=dict)
    client_profile: dict[str, Any] = Field(default_factory=dict)
    asset_profile: dict[str, Any] = Field(default_factory=dict)
    quote_template: Template | dict[str, Any] | None = None
    policy_rules: dict[str, Any] = Field(default_factory=dict)
    external_reference_data: dict[str, Any] = Field(default_factory=dict)


class QuoteDomainPayload(BaseModel):
    """Quote-specific payloads consumed by generation and review modules."""

    quote_intake_payload: dict[str, Any] = Field(default_factory=dict)
    quote_generation_payload: dict[str, Any] = Field(default_factory=dict)
    approval_decision: dict[str, Any] = Field(default_factory=dict)
    rule_outcomes: dict[str, Any] = Field(default_factory=dict)
    quote_evaluation: dict[str, Any] = Field(default_factory=dict)


class QuotePricingOutput(BaseModel):
    """Pricing output produced during quote generation."""

    base_premium_ron: float | None = None
    adjustments: list[dict[str, Any]] = Field(default_factory=list)
    final_premium_ron: float | None = None
    base_premium: float | None = None
    pricing_adjustments: list[dict[str, Any]] = Field(default_factory=list)
    deductible_adjustments: list[dict[str, Any]] = Field(default_factory=list)
    final_premium: float | None = None
    calculation_steps: list[dict[str, Any]] = Field(default_factory=list)
    rule_version: str | None = None
    pricing_rationale: list[str] = Field(default_factory=list)
    currency: str = "RON"
    calculation_year: int | None = None
    pricing_metadata: dict[str, Any] = Field(default_factory=dict)


class QuoteDocumentOutput(BaseModel):
    """Unsigned quote document generated before signing."""

    draft_quote: str | None = None
    rendered_template_text: str | None = None
    final_document_text: str | None = None
    template_used: dict[str, Any] = Field(default_factory=dict)
    template_version: str | None = None
    mapped_input_fields: dict[str, Any] = Field(default_factory=dict)
    unmapped_or_missing_fields: list[str] = Field(default_factory=list)
    generation_rationale: str | None = None
    llm_drafting_summary: str | None = None
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    quote_document_reference: dict[str, Any] = Field(default_factory=dict)


class QuoteGeneratedOutputs(BaseModel):
    """Generated artifacts produced during quote generation."""

    pricing_outputs: QuotePricingOutput = Field(default_factory=QuotePricingOutput)
    quote_document: QuoteDocumentOutput = Field(default_factory=QuoteDocumentOutput)
    ai_insights: dict[str, Any] = Field(default_factory=dict)
    underwriting_summary: str | None = None


class QuoteChecksAndWarnings(BaseModel):
    """Validation and underwriting warnings for a quote case."""

    quote_warnings: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    rule_warnings: list[str] = Field(default_factory=list)
    pricing_warnings: list[str] = Field(default_factory=list)
    review_warnings: list[str] = Field(default_factory=list)


class QuoteGuidance(BaseModel):
    """Human-facing guidance that is not generated quote output."""

    quote_guidance: dict[str, Any] = Field(default_factory=dict)


class QuoteExternalSignals(BaseModel):
    """External signals reserved for future enrichment of quote cases."""

    location_signals: dict[str, Any] = Field(default_factory=dict)
    asset_signals: dict[str, Any] = Field(default_factory=dict)
    risk_signals: dict[str, Any] = Field(default_factory=dict)
    regulatory_signals: dict[str, Any] = Field(default_factory=dict)


class QuoteReviewState(BaseModel):
    """Review-screen state derived from the quote case context."""

    quote_review_view: Any | None = None
    available_actions: list[str] = Field(default_factory=list)


class QuoteCaseContext(BaseCaseContext):
    """Concrete Underwright case context for quote generation."""

    case_metadata: QuoteCaseMetadata = Field(default_factory=QuoteCaseMetadata)
    source_inputs: QuoteSourceInputs = Field(default_factory=QuoteSourceInputs)
    reference_data: QuoteReferenceData = Field(default_factory=QuoteReferenceData)
    domain_payload: QuoteDomainPayload = Field(default_factory=QuoteDomainPayload)
    generated_outputs: QuoteGeneratedOutputs = Field(
        default_factory=QuoteGeneratedOutputs
    )
    checks_and_warnings: QuoteChecksAndWarnings = Field(
        default_factory=QuoteChecksAndWarnings
    )
    guidance: QuoteGuidance = Field(default_factory=QuoteGuidance)
    external_signals: QuoteExternalSignals = Field(default_factory=QuoteExternalSignals)
    review_state: QuoteReviewState = Field(default_factory=QuoteReviewState)


__all__ = [
    "QuoteCaseContext",
    "QuoteCaseMetadata",
    "QuoteChecksAndWarnings",
    "QuoteDocumentOutput",
    "QuoteDomainPayload",
    "QuoteExternalSignals",
    "QuoteGeneratedOutputs",
    "QuoteGuidance",
    "QuotePricingOutput",
    "QuoteReferenceData",
    "QuoteReviewState",
    "QuoteSourceInputs",
]
