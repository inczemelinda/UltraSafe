from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from underwright.domain.models import Template


NormalizationStatus = Literal[
    "normalized",
    "parser_failed",
    "suppressed_non_legislative",
    "duplicate_unchanged",
    "skipped_missing_required_fields",
]
SuppressionStatus = Literal[
    "parser_failed",
    "suppressed_non_legislative",
    "duplicate_unchanged",
    "skipped_missing_required_fields",
]
LegalDocumentTemplateMatchType = Literal[
    "amended_reference",
    "repealed_reference",
    "direct_reference",
    "keyword_topic",
]
LegalDocumentReviewStatus = Literal["needs_review", "accepted", "dismissed"]
TemplateChangeSuggestionStatus = Literal[
    "draft",
    "accepted",
    "rejected",
    "superseded",
    "applied_to_draft",
]
TemplateChangeSuggestionHunkStatus = Literal["draft", "accepted", "rejected", "edited"]
TemplateChangeType = Literal[
    "replace",
    "insert_before",
    "insert_after",
    "delete",
    "manual_review",
]
WordingDocumentImpactConfidence = Literal["high", "medium", "low"]
WordingDocumentChangeTarget = Literal["full_text", "structured_clause"]


class NormalizedLegalDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raw_source_item_id: UUID
    source_id: str
    source_key: str
    jurisdiction: str
    parser_id: str
    canonical_url: str
    source_url: str
    external_identifier: str | None = None
    title: str
    language: str | None = None
    issuer: str | None = None
    instrument_type: str | None = None
    instrument_number: str | None = None
    instrument_year: int | None = None
    instrument_date: date | None = None
    publication_reference: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    status: str | None = None
    legal_references: list[dict[str, Any] | str] = Field(default_factory=list)
    structured_clauses: list[dict[str, Any]] = Field(default_factory=list)
    amends: list[dict[str, Any] | str] = Field(default_factory=list)
    repeals: list[dict[str, Any] | str] = Field(default_factory=list)
    full_text: str
    summary: str | None = None
    document_hash: str
    extraction_confidence: float = Field(default=0, ge=0, le=1)
    parser_warnings: list[str] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class LegalDocumentNormalizationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raw_source_item_id: UUID
    source_id: str
    parser_id: str
    normalized_legal_document_id: UUID | None = None
    status: NormalizationStatus
    reason: str | None = None
    parser_warnings: list[str] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class LegalDocumentNormalizationBatchResult(BaseModel):
    source_id: str | None = None
    status: Literal["success", "partial_failure", "failed"] = "success"
    raw_items_seen: int = 0
    normalized: int = 0
    suppressed: int = 0
    skipped_missing_required_fields: int = 0
    duplicate_unchanged: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class LegalDocumentTemplateReviewCandidate(BaseModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    normalized_legal_document_id: UUID
    template_id: int
    template_code: str
    template_name: str
    template_version: str
    template_version_hash: str
    match_type: LegalDocumentTemplateMatchType
    matched_reference: str | None = None
    review_reason: str
    confidence: float = Field(ge=0, le=1)
    status: LegalDocumentReviewStatus = "needs_review"
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class LegalDocumentTemplateReviewItem(BaseModel):
    legal_document: NormalizedLegalDocument
    candidates: list[LegalDocumentTemplateReviewCandidate] = Field(default_factory=list)
    affected_template_count: int = 0
    highest_confidence: float = Field(default=0, ge=0, le=1)
    wording_document_impacts: list["WordingDocumentImpact"] = Field(
        default_factory=list
    )


class LegalDocumentTemplateCorrelationBatchResult(BaseModel):
    source_id: str | None = None
    status: Literal["success", "partial_failure", "failed"] = "success"
    legal_documents_seen: int = 0
    templates_seen: int = 0
    candidates_created: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class TemplateChangeSuggestionHunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    suggestion_id: UUID
    section_id: str | None = None
    section_label: str | None = None
    template_section_title: str | None = None
    template_article_title: str | None = None
    before_context: str | None = None
    after_context: str | None = None
    full_context_excerpt: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    change_type: TemplateChangeType
    old_text: str
    new_text: str
    rationale: str
    source_reference: str
    confidence: float = Field(ge=0, le=1)
    status: TemplateChangeSuggestionHunkStatus = "draft"
    reviewer_notes: str | None = None


class TemplateChangeSuggestion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    template_id: int
    normalized_legal_document_id: UUID
    template_version_hash: str
    status: TemplateChangeSuggestionStatus = "draft"
    overall_summary: str
    validation_result: dict[str, Any] = Field(default_factory=dict)
    hunks: list[TemplateChangeSuggestionHunk] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TemplateDraftRevision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    suggestion_id: UUID
    template_id: int
    template_code: str
    template_name: str
    base_template_version: str
    base_template_version_hash: str
    status: Literal[
        "draft",
        "submitted_for_approval",
        "accepted",
        "rejected",
        "superseded",
    ] = "draft"
    base_content: str
    revised_content: str
    applied_hunk_ids: list[UUID] = Field(default_factory=list)
    validation_result: dict[str, Any] = Field(default_factory=dict)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WordingDocumentProposedChange(BaseModel):
    target: WordingDocumentChangeTarget
    clause_id: str | None = None
    current_text: str
    proposed_text: str
    rationale: str
    diff: str
    safe_to_auto_draft: bool = False


class WordingDocumentImpact(BaseModel):
    wording_document_id: int | None = None
    wording_document_code: str
    wording_document_title: str
    current_published_version_id: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    affected_clause_ids: list[str] = Field(default_factory=list)
    affected_legal_references: list[str] = Field(default_factory=list)
    matched_text_snippets: list[str] = Field(default_factory=list)
    match_reason: str
    confidence: WordingDocumentImpactConfidence
    confidence_score: float = Field(default=0, ge=0, le=1)
    proposed_changes: list[WordingDocumentProposedChange] = Field(
        default_factory=list
    )
    safe_to_auto_draft: bool = False


class WordingDocumentDraftComparison(BaseModel):
    wording_document_id: int
    current_published_version_id: int | None = None
    draft_version_id: int
    added_clauses: list[str] = Field(default_factory=list)
    removed_clauses: list[str] = Field(default_factory=list)
    modified_clauses: list[str] = Field(default_factory=list)
    changed_legal_references: list[str] = Field(default_factory=list)
    changed_effective_dates: list[str] = Field(default_factory=list)
    changed_full_text_snippets: list[str] = Field(default_factory=list)
    content_hash_changed: bool = False
    proposed_changes: list[WordingDocumentProposedChange] = Field(
        default_factory=list
    )


class TemplateChangeSuggestionDetail(BaseModel):
    suggestion: TemplateChangeSuggestion
    candidate: LegalDocumentTemplateReviewCandidate
    normalized_legal_document: NormalizedLegalDocument
    template: Template
    draft_revision: TemplateDraftRevision | None = None


class SuppressionResult(BaseModel):
    raw_source_item_id: UUID
    source_id: str
    parser_id: str
    status: SuppressionStatus
    reason: str
    parser_warnings: list[str] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
