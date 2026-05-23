from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from underwright.domain.case_context_base import _utc_now


ClaimSeverity = Literal["low", "medium", "high"]
ReviewFindingSeverity = Literal["info", "low", "medium", "warning", "high"]
DocumentConsistencyStatus = Literal[
    "no_discrepancies",
    "discrepancies_found",
    "insufficient_document_data",
]
EvidenceRequirementStatus = Literal[
    "satisfied",
    "missing",
    "insufficient",
    "not_applicable",
]
EvidenceRequirementNextAction = Literal[
    "request_evidence",
    "manual_review",
    "underwriter_review",
]
EvidenceRequestDraftStatus = Literal["draft", "sent"]
EvidenceRequestSendStatus = Literal["not_sent", "mock_sent", "sent", "failed"]
ClaimCommunicationSuggestionStatus = Literal[
    "new",
    "reviewed",
    "draft_created",
    "dismissed",
    "sent",
]
EvidenceRefreshStatus = Literal["pending", "completed", "failed"]
CoverageStatus = Literal[
    "potentially_covered",
    "not_covered",
    "excluded",
    "unclear",
    "insufficient_information",
    "covered",
    "requires_review",
]
CoverageConfidence = Literal["high", "medium", "low"]


class ClaimValidationOutput(BaseModel):
    is_valid: bool
    missing_required_fields: list[str] = Field(default_factory=list)
    attachment_warnings: list[str] = Field(default_factory=list)
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)


class ClaimClassificationOutput(BaseModel):
    claim_type: str
    category: str
    severity: ClaimSeverity
    rationale: str
    review_flags: list[str] = Field(default_factory=list)


class ClaimSummaryOutput(BaseModel):
    summary: str
    key_facts: dict[str, Any] = Field(default_factory=dict)
    recommended_next_steps: list[str] = Field(default_factory=list)


class ClaimConfidenceOutput(BaseModel):
    score: int
    rationale: list[str] = Field(default_factory=list)
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)


class ExtractedClaimDocument(BaseModel):
    document_id: UUID | str
    filename: str
    document_type: str
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: float = Field(ge=0, le=1)
    source: str | None = None
    extraction_status: str = "completed"
    extraction_provenance: str = "actual"
    extraction_message: str | None = None
    extraction_metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedDocumentBundle(BaseModel):
    documents: list[ExtractedClaimDocument] = Field(default_factory=list)
    source: str | None = None
    extraction_status: str = "completed"
    extraction_provenance: str = "actual"


class DocumentSupportingFact(BaseModel):
    field: str
    claim_value: Any | None = None
    document_value: Any | None = None
    source_document: UUID | str | None = None
    severity: ReviewFindingSeverity = "info"
    message: str


class DocumentDiscrepancy(BaseModel):
    field: str
    claim_value: Any | None = None
    document_value: Any | None = None
    source_document: UUID | str | None = None
    severity: ReviewFindingSeverity = "medium"
    message: str


class DocumentConsistencyResult(BaseModel):
    status: DocumentConsistencyStatus = "insufficient_document_data"
    supporting_facts: list[DocumentSupportingFact] = Field(default_factory=list)
    discrepancies: list[DocumentDiscrepancy] = Field(default_factory=list)


class EvidenceRequirement(BaseModel):
    requirement_type: str
    reason: str
    acceptable_documents: list[str] = Field(default_factory=list)
    severity: ReviewFindingSeverity = "medium"
    status: EvidenceRequirementStatus = "missing"
    suggested_next_action: str | None = None


class EvidenceRequirementResult(BaseModel):
    required_evidence: list[EvidenceRequirement] = Field(default_factory=list)
    suggested_next_action: EvidenceRequirementNextAction | None = None
    rationale: str | None = None
    summary: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_requirements_alias(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and "required_evidence" not in data
            and "requirements" in data
        ):
            return {**data, "required_evidence": data["requirements"]}
        return data

    @property
    def requirements(self) -> list[EvidenceRequirement]:
        return self.required_evidence


class EvidenceRequestDraft(BaseModel):
    """Underwriter-editable request for evidence; not an email send record."""

    draft_id: UUID | str = Field(default_factory=uuid4)
    claim_request_id: UUID | str
    subject: str
    body: str
    recipients: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    status: EvidenceRequestDraftStatus = "draft"
    source_suggestion_id: str | None = None
    requested_document_type: str | None = None
    due_date: str | None = None
    send_status: EvidenceRequestSendStatus = "not_sent"
    sent_at: datetime | None = None
    sent_to: list[str] = Field(default_factory=list)
    provider_message_id: str | None = None
    email_message_id: UUID | str | None = None
    reply_token: str | None = None
    send_error_message: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class ClaimCommunicationSuggestionState(BaseModel):
    """Human lifecycle state for an AI communication suggestion."""

    suggestion_id: str
    status: ClaimCommunicationSuggestionStatus = "new"
    source: str = "underwriter"
    draft_id: UUID | str | None = None
    dismissed_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class ReceivedEvidenceAttachment(BaseModel):
    filename: str
    storage_key: str | None = None
    document_id: UUID | str | None = None
    content_type: str | None = None


class ReceivedClaimEvidence(BaseModel):
    evidence_request_id: UUID | str | None = None
    sender_email: str
    message_body: str | None = None
    attachments: list[ReceivedEvidenceAttachment] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=_utc_now)
    source: str = "email_hook"
    refresh_status: EvidenceRefreshStatus = "pending"


class PolicyWordingSection(BaseModel):
    section_id: str
    title: str
    text: str
    coverage_tags: list[str] = Field(default_factory=list)
    exclusion_tags: list[str] = Field(default_factory=list)


class CoverageAssessmentResult(BaseModel):
    """Structured wording-fit pre-check for human review, not a final decision."""

    coverage_status: CoverageStatus
    matched_wording_sections: list[str] = Field(default_factory=list)
    wording_section_ids: list[str] = Field(default_factory=list)
    possible_exclusions: list[str] = Field(default_factory=list)
    rationale: str
    confidence: CoverageConfidence = "low"
    assessed_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_numeric_confidence(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        confidence = data.get("confidence")
        if isinstance(confidence, (int, float)):
            if confidence >= 0.75:
                return {**data, "confidence": "high"}
            if confidence >= 0.45:
                return {**data, "confidence": "medium"}
            return {**data, "confidence": "low"}
        return data


class ClaimReviewFindings(BaseModel):
    coverage_assessment: CoverageAssessmentResult | None = None
    document_consistency: DocumentConsistencyResult = Field(
        default_factory=DocumentConsistencyResult
    )
    evidence_requirements: EvidenceRequirementResult = Field(
        default_factory=EvidenceRequirementResult
    )
    suggested_next_action: str | None = None
    human_readable_summary: str | None = None


__all__ = [
    "ClaimCommunicationSuggestionState",
    "ClaimCommunicationSuggestionStatus",
    "ClaimClassificationOutput",
    "ClaimConfidenceOutput",
    "ClaimReviewFindings",
    "ClaimSeverity",
    "ClaimSummaryOutput",
    "ClaimValidationOutput",
    "CoverageAssessmentResult",
    "CoverageConfidence",
    "CoverageStatus",
    "DocumentConsistencyStatus",
    "DocumentConsistencyResult",
    "DocumentDiscrepancy",
    "DocumentSupportingFact",
    "EvidenceRequirement",
    "EvidenceRequirementNextAction",
    "EvidenceRequirementResult",
    "EvidenceRequirementStatus",
    "EvidenceRequestDraft",
    "EvidenceRequestSendStatus",
    "EvidenceRequestDraftStatus",
    "EvidenceRefreshStatus",
    "ExtractedClaimDocument",
    "ExtractedDocumentBundle",
    "PolicyWordingSection",
    "ReceivedClaimEvidence",
    "ReceivedEvidenceAttachment",
    "ReviewFindingSeverity",
]
