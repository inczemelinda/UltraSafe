"""Claim case-context models."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import BaseCaseContext, CaseMetadata
from underwright.domain.claim_analysis import (
    ClaimCommunicationSuggestionState,
    ClaimClassificationOutput,
    ClaimConfidenceOutput,
    ClaimReviewFindings,
    ClaimSummaryOutput,
    ClaimValidationOutput,
    CoverageAssessmentResult,
    DocumentConsistencyResult,
    EvidenceRequirementResult,
    EvidenceRequestDraft,
    ExtractedDocumentBundle,
    ReceivedClaimEvidence,
)


class ClaimCaseMetadata(CaseMetadata):
    """Metadata defaults for the Underwright claim AI review workflow."""

    domain: Literal["claims"] = "claims"
    workflow_name: Literal["claim_ai_review"] = "claim_ai_review"


class ClaimSourceInputs(BaseModel):
    """Inputs that can start or parameterize claim AI review."""

    request_id: UUID | None = None
    client_id: int | str | UUID | None = None
    claim_id: int | str | UUID | None = None
    policy_id: int | str | UUID | None = None
    language: str | None = None
    user_entered_overrides: dict[str, Any] = Field(default_factory=dict)


class ClaimReferenceData(BaseModel):
    """Reference data loaded before claim AI review."""

    claim_request: dict[str, Any] = Field(default_factory=dict)
    client_profile: dict[str, Any] = Field(default_factory=dict)
    policy_profile: dict[str, Any] = Field(default_factory=dict)
    claim_history: list[dict[str, Any]] = Field(default_factory=list)
    external_reference_data: dict[str, Any] = Field(default_factory=dict)
    extracted_documents: ExtractedDocumentBundle = Field(
        default_factory=ExtractedDocumentBundle
    )
    received_evidence: list[ReceivedClaimEvidence] = Field(default_factory=list)


class ClaimDomainPayload(BaseModel):
    """Claim-specific payloads consumed by claim AI review modules."""

    claim_intake_payload: dict[str, Any] = Field(default_factory=dict)
    ai_review_payload: dict[str, Any] = Field(default_factory=dict)


class ClaimReviewOutput(BaseModel):
    """AI review output written during claim analysis.

    `recommendation` is retained for backward compatibility only. New claim
    review code should treat it as suggested-next-action text, not as final
    accept/reject decisioning.
    """

    review_summary: str | None = None
    recommendation: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    extracted_claim_facts: dict[str, Any] = Field(default_factory=dict)
    coverage_findings: dict[str, Any] = Field(default_factory=dict)
    fraud_indicators: list[str] = Field(default_factory=list)
    findings: ClaimReviewFindings | None = None
    generation_metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimGeneratedOutputs(BaseModel):
    """Generated artifacts produced during claim AI review."""

    validation: ClaimValidationOutput | None = None
    classification: ClaimClassificationOutput | None = None
    summary: ClaimSummaryOutput | None = None
    coverage_assessment: CoverageAssessmentResult | None = None
    document_consistency: DocumentConsistencyResult | None = None
    evidence_requirements: EvidenceRequirementResult | None = None
    evidence_request_draft: EvidenceRequestDraft | None = None
    communication_suggestion_states: dict[str, ClaimCommunicationSuggestionState] = (
        Field(default_factory=dict)
    )
    confidence: ClaimConfidenceOutput | None = None
    claim_review: ClaimReviewOutput = Field(default_factory=ClaimReviewOutput)


class ClaimChecksAndWarnings(BaseModel):
    """Validation and review warnings for a claim case."""

    claim_warnings: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    inconsistent_input_values: list[str] = Field(default_factory=list)
    attachment_warnings: list[str] = Field(default_factory=list)
    review_warnings: list[str] = Field(default_factory=list)


class ClaimGuidance(BaseModel):
    """Human-facing guidance that is not generated review output."""

    claim_guidance: dict[str, Any] = Field(default_factory=dict)


class ClaimExternalSignals(BaseModel):
    """External signals reserved for future enrichment of claim cases."""

    weather_signals: dict[str, Any] = Field(default_factory=dict)
    location_signals: dict[str, Any] = Field(default_factory=dict)
    fraud_signals: dict[str, Any] = Field(default_factory=dict)
    regulatory_signals: dict[str, Any] = Field(default_factory=dict)


class ClaimReviewState(BaseModel):
    """Review-screen state derived from the claim case context."""

    claim_review_view: Any | None = None
    available_actions: list[str] = Field(default_factory=list)


class ClaimCaseContext(BaseCaseContext):
    """Concrete Underwright case context for claim AI review."""

    case_metadata: ClaimCaseMetadata = Field(default_factory=ClaimCaseMetadata)
    source_inputs: ClaimSourceInputs = Field(default_factory=ClaimSourceInputs)
    reference_data: ClaimReferenceData = Field(default_factory=ClaimReferenceData)
    domain_payload: ClaimDomainPayload = Field(default_factory=ClaimDomainPayload)
    generated_outputs: ClaimGeneratedOutputs = Field(
        default_factory=ClaimGeneratedOutputs
    )
    checks_and_warnings: ClaimChecksAndWarnings = Field(
        default_factory=ClaimChecksAndWarnings
    )
    guidance: ClaimGuidance = Field(default_factory=ClaimGuidance)
    external_signals: ClaimExternalSignals = Field(default_factory=ClaimExternalSignals)
    review_state: ClaimReviewState = Field(default_factory=ClaimReviewState)


__all__ = [
    "ClaimCaseContext",
    "ClaimCaseMetadata",
    "ClaimChecksAndWarnings",
    "ClaimDomainPayload",
    "ClaimExternalSignals",
    "ClaimGeneratedOutputs",
    "ClaimGuidance",
    "ClaimReferenceData",
    "ClaimReviewOutput",
    "ClaimReviewState",
    "ClaimSourceInputs",
]
