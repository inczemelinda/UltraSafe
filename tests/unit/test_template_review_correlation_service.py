from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from underwright.application.services.template_review_correlation_service import (
    TemplateReviewCorrelationService,
)
from underwright.domain.intelligence import (
    AuditRecord,
    ExternalEvent,
    TemplateReviewCandidate,
)
from underwright.domain.models import Template


class FakeEventRepository:
    def __init__(
        self,
        events: list[ExternalEvent] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.events = events or []
        self.error = error
        self.limit = None
        self.source_id = None

    def list_for_template_review(self, limit: int, source_id: str | None = None):
        self.limit = limit
        self.source_id = source_id
        if self.error is not None:
            raise self.error
        return self.events[:limit]


class FakeTemplateRepository:
    def __init__(self, templates: list[Template]) -> None:
        self.templates = templates

    def list_active(self):
        return self.templates


class FakeCandidateRepository:
    def __init__(self, inserted: bool = True) -> None:
        self.inserted = inserted
        self.candidates = []

    def save_if_new(self, candidate):
        self.candidates.append(candidate)
        return self.inserted


class FakeAuditRepository:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def save(self, record):
        self.records.append(record)
        return record


class FakeCandidateExplainer:
    model_name = "ai-template-explainer"
    model_version = "test-model"
    prompt_version = "test-prompt"

    def explain(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> TemplateReviewCandidate:
        return candidate.model_copy(
            update={
                "rationale": (
                    "Review recommended because the event and template share a legal "
                    "reference, so the wording is potentially affected."
                )
            }
        )


class FailingCandidateExplainer(FakeCandidateExplainer):
    def explain(
        self,
        event: ExternalEvent,
        template: Template,
        candidate: TemplateReviewCandidate,
    ) -> TemplateReviewCandidate:
        raise RuntimeError("explainer unavailable")


def make_event(
    body_text: str = "ASF mentioneaza Legea 260/2008 si PAD.",
    topics: list[str] | None = None,
) -> ExternalEvent:
    now = datetime(2026, 5, 8, 9, 0, tzinfo=UTC)
    return ExternalEvent(
        event_id=UUID("50000000-0000-0000-0000-000000000001"),
        raw_item_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_id="asf_ro",
        source_type="regulator",
        trust_tier="authoritative",
        original_url="https://asfromania.ro/item",
        ingested_at=now,
        title="ASF actualizare Legea 260/2008",
        body_text=body_text,
        original_language="ro",
        country="RO",
        jurisdiction="RO",
        event_type="regulatory_update",
        line_of_business="property",
        topics_json=(
            ["PAD / compulsory home insurance"] if topics is None else topics
        ),
        severity="medium",
        confidence=0.8,
        underwriter_summary="Potentially relevant to PAD.",
        recommended_action="Review recommended for potentially affected Romanian property work.",
        status="classified",
    )


def make_template(
    content: str = "Contract PAD guvernat de Legea 260/2008.",
    template_code: str = "PAD_STANDARD_RO",
    name: str = "PAD Standard RO",
) -> Template:
    return Template(
        id=22,
        template_code=template_code,
        name=name,
        version="1.0",
        document_type="insurance_contract",
        is_active=True,
        content=content,
        created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )


def test_correlate_batch_creates_candidate_for_legal_reference_overlap() -> None:
    candidate_repo = FakeCandidateRepository()
    audit_repo = FakeAuditRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([make_event()]),
        template_repository=FakeTemplateRepository([make_template()]),
        candidate_repository=candidate_repo,
        audit_repository=audit_repo,
    )

    result = service.correlate_batch(limit=5, source_id="asf_ro")

    assert result.status == "success"
    assert result.events_seen == 1
    assert result.templates_seen == 1
    assert result.candidates_created == 1
    candidate = candidate_repo.candidates[0]
    assert "legal_reference_overlap" in candidate.rule_ids_json
    assert "Legea 260/2008" in candidate.legal_references_json
    assert "Review recommended" in candidate.rationale
    assert "must" not in candidate.rationale.lower()
    assert audit_repo.records[0].rules_triggered_json == candidate.rule_ids_json


def test_correlate_batch_uses_optional_ai_explainer_after_rule_match() -> None:
    candidate_repo = FakeCandidateRepository()
    audit_repo = FakeAuditRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([make_event()]),
        template_repository=FakeTemplateRepository([make_template()]),
        candidate_repository=candidate_repo,
        audit_repository=audit_repo,
        candidate_explainer=FakeCandidateExplainer(),
    )

    result = service.correlate_batch(limit=5)

    assert result.candidates_created == 1
    candidate = candidate_repo.candidates[0]
    assert "potentially affected" in candidate.rationale
    assert audit_repo.records[0].model_name == "ai-template-explainer"


def test_correlate_batch_keeps_candidate_when_ai_explainer_fails() -> None:
    candidate_repo = FakeCandidateRepository()
    audit_repo = FakeAuditRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([make_event()]),
        template_repository=FakeTemplateRepository([make_template()]),
        candidate_repository=candidate_repo,
        audit_repository=audit_repo,
        candidate_explainer=FailingCandidateExplainer(),
    )

    result = service.correlate_batch(limit=5)

    assert result.candidates_created == 1
    assert "Review recommended" in candidate_repo.candidates[0].rationale
    assert (
        "explainer unavailable"
        in audit_repo.records[0].input_ref_json["candidate_explainer_error"]
    )


def test_correlate_batch_creates_candidate_for_topic_overlap() -> None:
    event = make_event(body_text="ASF mentioneaza PAD.", topics=["earthquake"])
    template = make_template(content="Clauza de cutremur pentru contracte property.")
    candidate_repo = FakeCandidateRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([event]),
        template_repository=FakeTemplateRepository([template]),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=5)

    assert result.candidates_created == 1
    assert candidate_repo.candidates[0].rule_ids_json == ["template_topic_overlap"]


def test_correlate_batch_skips_templates_without_overlap() -> None:
    candidate_repo = FakeCandidateRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([make_event()]),
        template_repository=FakeTemplateRepository(
            [
                make_template(
                    content="Template RCA fara referinte relevante.",
                    template_code="RCA_STANDARD_RO",
                    name="RCA Standard RO",
                )
            ]
        ),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=5)

    assert result.candidates_created == 0
    assert candidate_repo.candidates == []


def test_correlate_batch_skips_events_without_topics_or_legal_references() -> None:
    event = make_event(body_text="Generic page without useful matching signal.", topics=[])
    event.title = "Generic Page"
    candidate_repo = FakeCandidateRepository()
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository([event]),
        template_repository=FakeTemplateRepository([make_template()]),
        candidate_repository=candidate_repo,
    )

    result = service.correlate_batch(limit=5)

    assert result.candidates_created == 0
    assert candidate_repo.candidates == []


def test_correlate_batch_returns_failed_when_setup_fails() -> None:
    service = TemplateReviewCorrelationService(
        event_repository=FakeEventRepository(error=RuntimeError("db unavailable")),
        template_repository=FakeTemplateRepository([]),
        candidate_repository=FakeCandidateRepository(),
    )

    result = service.correlate_batch(limit=5)

    assert result.status == "failed"
    assert result.errors == ["db unavailable"]
