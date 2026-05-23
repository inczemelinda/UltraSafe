from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


CountryCode = Literal["RO", "EU"]
LineOfBusiness = Literal[
    "property",
    "health",
    "life",
    "auto",
    "liability",
    "travel",
    "other",
]
Severity = Literal["low", "medium", "high"]
TrustTier = Literal["authoritative", "trusted", "unverified"]
SourceType = Literal[
    "address_data",
    "building_seismic_risk",
    "cadastral_data",
    "climate_data",
    "flood_hazard",
    "geospatial_data",
    "regulator",
    "legal_portal",
    "official_journal",
    "news",
    "weather",
    "market_data",
    "insurance_pool",
    "seismic_data",
    "seismic_hazard",
    "statistical_data",
]
ConnectorType = Literal["web_scrape", "api", "feed", "manual"]

EventType = Literal[
    "regulatory_update",
    "market_report",
    "sanction_or_enforcement",
    "consumer_protection",
    "claims_update",
    "solvency_or_market_stability",
    "product_or_coverage_update",
    "public_warning",
    "consultation_or_draft_rule",
    "not_relevant",
]

CorrelationTargetType = Literal["document_asset", "underwriting_work_item"]
CorrelationStatus = Literal["candidate", "accepted", "dismissed"]
AlertStatus = Literal["open", "acknowledged", "dismissed"]
WorkItemType = Literal["renewal", "submission"]
FeedbackType = Literal[
    "relevant",
    "not_relevant",
    "wrong_topic",
    "wrong_severity",
    "create_review_task",
    "dismiss",
]


class Source(BaseModel):
    source_id: str
    name: str
    country: CountryCode
    source_type: SourceType
    trust_tier: TrustTier
    connector_type: ConnectorType
    language: str
    enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)
    last_successful_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class Attachment(BaseModel):
    url: str
    filename: str | None = None
    content_type: str | None = None
    extracted_text: str | None = None
    fetch_status: str = "pending"


class RawSourceItem(BaseModel):
    raw_item_id: UUID = Field(default_factory=uuid4)
    source_id: str
    original_url: str
    canonical_url: str
    published_at: datetime | None = None
    fetched_at: datetime
    title: str
    raw_html: str | None = None
    extracted_text: str
    attachments_json: list[Attachment] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    fetch_status: str = "success"
    parse_status: str = "success"
    error_message: str | None = None
    created_at: datetime


class EvidenceSnippet(BaseModel):
    snippet: str
    reason: str


class ClassificationOutput(BaseModel):
    is_insurance_relevant: bool
    is_property_relevant: bool
    event_type: EventType
    display_title: str | None = None
    topics: list[str] = Field(default_factory=list)
    affected_products: list[str] = Field(default_factory=list)
    affected_perils: list[str] = Field(default_factory=list)
    severity: Severity = "low"
    summary_for_underwriter: str
    recommended_action: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceSnippet] = Field(default_factory=list)
    reasons_for_suppression: list[str] = Field(default_factory=list)


class SummaryOutput(BaseModel):
    display_title: str = Field(min_length=1)
    summary_for_underwriter: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class ClassificationInput(BaseModel):
    raw_item_id: UUID
    source_id: str
    source_type: SourceType
    trust_tier: TrustTier
    original_url: str
    published_at: datetime | None = None
    title: str
    body_text_ref: str
    body_text: str
    original_language: str
    country: CountryCode
    jurisdiction: str
    source_url_host: str | None = None
    allowed_source_hosts: list[str] = Field(default_factory=list)
    is_allowed_source_url: bool = True


class ExternalEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    raw_item_id: UUID
    source_id: str
    source_type: SourceType
    trust_tier: TrustTier
    original_url: str
    published_at: datetime | None = None
    ingested_at: datetime
    title: str
    body_text_ref: str | None = None
    body_text: str
    original_language: str
    country: CountryCode
    jurisdiction: str
    event_type: EventType = "not_relevant"
    line_of_business: LineOfBusiness | None = None
    product: str | None = None
    topics_json: list[str] = Field(default_factory=list)
    perils_json: list[str] = Field(default_factory=list)
    severity: Severity = "low"
    confidence: float = Field(default=0, ge=0, le=1)
    underwriter_summary: str = ""
    recommended_action: str = ""
    evidence_json: list[EvidenceSnippet] = Field(default_factory=list)
    classification_json: ClassificationOutput | None = None
    status: Literal["new", "classified", "suppressed", "failed"] = "new"


class DocumentAsset(BaseModel):
    document_id: UUID = Field(default_factory=uuid4)
    name: str
    type: str
    country: CountryCode
    line_of_business: LineOfBusiness
    product: str
    topics_json: list[str] = Field(default_factory=list)
    owner: str
    last_reviewed_at: datetime | None = None
    review_status: str = "current"
    created_at: datetime
    updated_at: datetime


class UnderwritingWorkItem(BaseModel):
    work_item_id: UUID = Field(default_factory=uuid4)
    type: WorkItemType
    account_name: str
    country: CountryCode
    county: str
    city: str
    line_of_business: LineOfBusiness
    product: str
    insured_value: float | None = None
    perils_json: list[str] = Field(default_factory=list)
    renewal_date: date
    assigned_underwriter: str
    status: str
    source_ref_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Correlation(BaseModel):
    correlation_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    target_type: CorrelationTargetType
    target_id: UUID
    rule_ids_json: list[str] = Field(default_factory=list)
    match_score: float = Field(default=0, ge=0, le=1)
    llm_rank: int | None = None
    rationale: str
    evidence_json: list[EvidenceSnippet] = Field(default_factory=list)
    status: CorrelationStatus = "candidate"
    created_at: datetime


class Alert(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    work_item_id: UUID
    assigned_underwriter: str
    title: str
    summary: str
    why_it_matters: str
    recommended_action: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    status: AlertStatus = "open"
    created_at: datetime


class Feedback(BaseModel):
    feedback_id: UUID = Field(default_factory=uuid4)
    user_id: str
    target_type: Literal["event", "alert", "correlation"]
    target_id: UUID
    feedback_type: FeedbackType
    comment: str | None = None
    created_at: datetime


class AuditRecord(BaseModel):
    audit_id: UUID = Field(default_factory=uuid4)
    entity_type: str
    entity_id: UUID | str
    action: str
    raw_url: str | None = None
    raw_item_id: UUID | None = None
    model_name: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    input_ref_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] = Field(default_factory=dict)
    rules_triggered_json: list[str] = Field(default_factory=list)
    user_id: str | None = None
    created_at: datetime


class IntelligenceFeedCard(BaseModel):
    event_id: UUID
    title: str
    asf_source_link: str
    published_at: datetime | None = None
    event_type: EventType
    topics: list[str]
    severity: Severity
    summary: str
    why_it_matters: str
    affected_renewals_count: int
    affected_documents: list[str]
    recommended_action: str
    confidence: float


class SourceLink(BaseModel):
    label: str
    url: str
    content_type: str | None = None


class InsightCard(BaseModel):
    event_id: UUID
    title: str
    paragraphs: list[str]
    source_links: list[SourceLink]
    published_at: datetime | None = None
    source_id: str
    source_name: str
    country: CountryCode
    line_of_business: LineOfBusiness | None = None
    event_type: EventType
    topics: list[str]
    severity: Severity
    confidence: float
    status: Literal["new", "classified", "suppressed", "failed"]


class TemplateReviewCandidate(BaseModel):
    candidate_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    template_id: int
    template_code: str
    template_name: str
    template_version: str
    event_title: str
    source_url: str
    legal_references_json: list[str] = Field(default_factory=list)
    rule_ids_json: list[str] = Field(default_factory=list)
    match_score: float = Field(default=0, ge=0, le=1)
    rationale: str
    evidence_json: list[EvidenceSnippet] = Field(default_factory=list)
    status: CorrelationStatus = "candidate"
    created_at: datetime


class EventDetail(BaseModel):
    event: ExternalEvent
    source: Source
    alerts: list[Alert]
    document_correlations: list[Correlation]
    audit_records: list[AuditRecord]


class IngestionRun(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    source_id: str
    status: Literal["started", "success", "failed"]
    raw_items_seen: int = 0
    raw_items_created: int = 0
    events_created: int = 0
    alerts_created: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None


class ProcessingBatchResult(BaseModel):
    source_id: str | None = None
    status: Literal["success", "failed"]
    raw_items_seen: int = 0
    events_created: int = 0
    classified: int = 0
    suppressed: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None


class TemplateCorrelationBatchResult(BaseModel):
    source_id: str | None = None
    status: Literal["success", "failed"]
    events_seen: int = 0
    templates_seen: int = 0
    candidates_created: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None
