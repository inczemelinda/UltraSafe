from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from underwright.application.services.source_item_processing_service import (
    ClassificationPreprocessor,
    DeterministicInsuranceClassifier,
    FallbackEventClassifier,
    SourceItemProcessingService,
    SummaryWritingEventClassifier,
)
from underwright.domain.intelligence import (
    AuditRecord,
    ClassificationInput,
    ClassificationOutput,
    ExternalEvent,
    RawSourceItem,
    Source,
)


class FakeSourceRepository:
    def __init__(self, sources: dict[str, Source]) -> None:
        self.sources = sources

    def get_enabled(self, source_id: str) -> Source:
        return self.sources[source_id]


class FakeRawItemRepository:
    def __init__(
        self,
        raw_items: list[RawSourceItem] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.raw_items = raw_items or []
        self.error = error
        self.limit = None
        self.source_id = None

    def list_unprocessed(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> list[RawSourceItem]:
        self.limit = limit
        self.source_id = source_id
        if self.error is not None:
            raise self.error
        return self.raw_items[:limit]


class FakeExternalEventRepository:
    def __init__(
        self,
        inserted_results: list[bool] | None = None,
        error_on_raw_item_id: UUID | None = None,
    ) -> None:
        self.inserted_results = list(inserted_results or [])
        self.error_on_raw_item_id = error_on_raw_item_id
        self.events: list[ExternalEvent] = []

    def save_if_new(self, event: ExternalEvent) -> bool:
        if event.raw_item_id == self.error_on_raw_item_id:
            raise RuntimeError("event insert failed")
        self.events.append(event)
        if self.inserted_results:
            return self.inserted_results.pop(0)
        return True


class FakeAuditRepository:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def save(self, record: AuditRecord) -> AuditRecord:
        self.records.append(record)
        return record


class FailingClassifier:
    model_name = "ai-classifier"
    model_version = "test-model"
    prompt_version = "test-prompt"

    def classify(
        self,
        classification_input: ClassificationInput,
    ) -> ClassificationOutput:
        raise RuntimeError("ai unavailable")


class FakeSummaryWriter:
    model_name = "fake-summary-writer"
    model_version = "test-summary-model"
    prompt_version = "test-summary-prompt"

    def __init__(self) -> None:
        self.calls = 0

    def summarize(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ClassificationOutput:
        self.calls += 1
        return classification.model_copy(
            update={
                "display_title": (
                    f"AI headline for {classification_input.title}."
                ),
                "summary_for_underwriter": (
                    f"AI summary for {classification_input.title}."
                ),
                "recommended_action": (
                    "AI review recommended for potentially affected property work."
                ),
            }
        )


class FailingSummaryWriter:
    model_name = "failing-summary-writer"
    model_version = "test-summary-model"
    prompt_version = "test-summary-prompt"

    def summarize(
        self,
        classification_input: ClassificationInput,
        classification: ClassificationOutput,
    ) -> ClassificationOutput:
        raise RuntimeError("ai summary unavailable")


def make_source(
    source_id: str = "asf_ro",
    config_json=None,
    source_type: str = "regulator",
    name: str = "ASF Romania",
) -> Source:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return Source(
        source_id=source_id,
        name=name,
        country="RO",
        source_type=source_type,
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json=config_json or {},
        created_at=now,
        updated_at=now,
    )


def make_raw_item(
    raw_item_id: UUID,
    title: str,
    text: str,
    source_id: str = "asf_ro",
) -> RawSourceItem:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return RawSourceItem(
        raw_item_id=raw_item_id,
        source_id=source_id,
        original_url=f"https://example.test/{raw_item_id}",
        canonical_url=f"https://example.test/{raw_item_id}",
        fetched_at=now,
        title=title,
        extracted_text=text,
        content_hash=str(raw_item_id),
        created_at=now,
    )


def test_preprocessor_normalizes_and_trims_text() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000001"),
        "  ASF   comunicare  ",
        "  Text   despre\n\nlocuinte   " * 20,
    )
    preprocessor = ClassificationPreprocessor(max_text_chars=30)

    classification_input = preprocessor.build(raw_item, source)

    assert classification_input.title == "ASF comunicare"
    assert "\n" not in classification_input.body_text
    assert "  " not in classification_input.body_text
    assert len(classification_input.body_text) <= 30
    assert classification_input.body_text_ref.endswith(":extracted_text")


def test_deterministic_classifier_marks_property_item_relevant() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000002"),
        "ASF comunicare PAD si cutremur",
        "Informatii despre asigurari de locuinte, PAD si cutremur.",
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification.is_insurance_relevant is True
    assert classification.is_property_relevant is True
    assert "PAD / compulsory home insurance" in classification.topics
    assert "earthquake" in classification.affected_perils
    assert "review recommended" in classification.recommended_action.lower()


def test_deterministic_classifier_summarizes_demo_draft_rule_context() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000010"),
        "ASF draft PAD wording update after earthquake exposure review",
        (
            "ASF published a draft proiect for consultation on PAD compulsory home "
            "insurance wording. The item discusses locuinte coverage, clauze for "
            "earthquake cutremur exposure, and deductible limits."
        ),
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification.event_type == "consultation_or_draft_rule"
    assert classification.severity == "medium"
    assert classification.reasons_for_suppression == []
    assert "PAD / compulsory home insurance" in classification.topics
    assert "earthquake" in classification.affected_perils
    assert "draft rule or consultation" in classification.summary_for_underwriter
    assert "wording and templates" in classification.recommended_action


def test_source_processing_classifies_legislatie_insurance_document_relevant() -> None:
    source = make_source(
        source_id="ro_portal_legislativ",
        source_type="legal_portal",
        name="Portal Legislativ Romania",
        config_json={
            "pipeline_domain": "legal_documents",
            "list_url": "https://legislatie.just.ro/",
            "allowed_detail_hosts": ["legislatie.just.ro"],
        },
    )
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000020"),
        "LEGE nr. 120/2026 privind asigurarea obligatorie PAD",
        (
            "Actul reglementează asigurări de locuințe PAD, brokeri și "
            "intermediari, notificarea de daună, despăgubiri, clauze de "
            "poliță, conformitate și modificări ale contractelor de asigurare."
        ),
        source_id="ro_portal_legislativ",
    )
    raw_item.original_url = "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
    event_repository = FakeExternalEventRepository()
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"ro_portal_legislativ": source}),
        raw_item_repository=FakeRawItemRepository([raw_item]),
        external_event_repository=event_repository,
        classifier=DeterministicInsuranceClassifier(),
    )

    result = service.process_batch(limit=10, source_id="ro_portal_legislativ")

    assert result.status == "success"
    assert result.classified == 1
    event = event_repository.events[0]
    assert event.status == "classified"
    assert event.event_type == "claims_update"
    assert event.line_of_business == "property"
    assert "PAD / compulsory home insurance" in event.topics_json
    assert "insurance brokerage" in event.topics_json
    assert "claims handling" in event.topics_json
    assert "coverage wording" in event.topics_json
    assert "regulatory compliance" in event.topics_json
    assert "contract template changes" in event.topics_json


def test_deterministic_classifier_summarizes_demo_storm_warning_context() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000011"),
        "ANM severe storm and hail warning for insured residential property",
        (
            "ANM issued a public warning avertizare for severe storm and grindina "
            "conditions. The notice mentions damage to home locuinte roofs and "
            "expected daune claims for residential property insurance."
        ),
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification.event_type == "public_warning"
    assert classification.severity == "high"
    assert "storm / hail" in classification.affected_perils
    assert "public warning" in classification.summary_for_underwriter
    assert "quotes, renewals, and claims" in classification.recommended_action


def test_deterministic_classifier_summarizes_demo_flood_report_context() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000012"),
        "PAID report on flood exposure and PAD premium affordability",
        (
            "PAID released a market report raport on flood inundatii exposure for "
            "PAD and home insurance portfolios. The report discusses premium prima "
            "affordability and coverage uptake for locuinte."
        ),
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification.event_type == "market_report"
    assert classification.severity == "medium"
    assert "flood" in classification.affected_perils
    assert "market report" in classification.summary_for_underwriter
    assert "pricing, appetite, and exposure" in classification.recommended_action


def test_deterministic_classifier_suppresses_non_property_items() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000003"),
        "ASF comunicare pensii private",
        "Informatii despre pensii private si fonduri.",
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification.event_type == "not_relevant"
    assert classification.is_property_relevant is False
    assert classification.topics == []
    assert "private pensions" in classification.reasons_for_suppression


def test_deterministic_classifier_suppresses_off_source_items_generically() -> None:
    source = make_source(config_json={"list_url": "https://asfromania.ro/list"})
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000008"),
        "External page about PAD",
        "Text despre asigurari de locuinte si PAD.",
    )
    raw_item.original_url = "https://external.example/page"
    classification_input = ClassificationPreprocessor().build(raw_item, source)

    classification = DeterministicInsuranceClassifier().classify(classification_input)

    assert classification_input.is_allowed_source_url is False
    assert classification.event_type == "not_relevant"
    assert classification.is_insurance_relevant is False
    assert classification.is_property_relevant is False
    assert classification.topics == []
    assert (
        "source URL is outside configured source hosts"
        in classification.reasons_for_suppression
    )


def test_summary_writing_classifier_replaces_relevant_summary_fields() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000013"),
        "ASF comunicare PAD si cutremur",
        "Informatii despre asigurari de locuinte, PAD si cutremur.",
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)
    writer = FakeSummaryWriter()
    classifier = SummaryWritingEventClassifier(
        classifier=DeterministicInsuranceClassifier(),
        summary_writer=writer,
    )

    classification = classifier.classify(classification_input)

    assert writer.calls == 1
    assert classification.event_type == "regulatory_update"
    assert classification.display_title.startswith("AI headline")
    assert classification.summary_for_underwriter.startswith("AI summary")
    assert classification.recommended_action.startswith("AI review recommended")
    assert classifier.last_error is None
    assert classifier.model_name.endswith("+fake-summary-writer")


def test_summary_writing_classifier_keeps_deterministic_summary_on_ai_failure() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000014"),
        "ASF comunicare PAD si cutremur",
        "Informatii despre asigurari de locuinte, PAD si cutremur.",
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)
    classifier = SummaryWritingEventClassifier(
        classifier=DeterministicInsuranceClassifier(),
        summary_writer=FailingSummaryWriter(),
    )

    classification = classifier.classify(classification_input)

    assert "was classified as" in classification.summary_for_underwriter
    assert classification.display_title is None
    assert "summary_error=RuntimeError: ai summary unavailable" == classifier.last_error


def test_summary_writing_classifier_skips_suppressed_items() -> None:
    source = make_source()
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000015"),
        "ASF comunicare pensii private",
        "Informatii despre pensii private si fonduri.",
    )
    classification_input = ClassificationPreprocessor().build(raw_item, source)
    writer = FakeSummaryWriter()
    classifier = SummaryWritingEventClassifier(
        classifier=DeterministicInsuranceClassifier(),
        summary_writer=writer,
    )

    classification = classifier.classify(classification_input)

    assert writer.calls == 0
    assert classification.event_type == "not_relevant"
    assert "suppressed" in classification.summary_for_underwriter


def test_process_batch_stores_ai_display_title_when_available() -> None:
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000016"),
        "ASF comunicare generica",
        "Asigurari de locuinte PAD si cutremur.",
    )
    event_repo = FakeExternalEventRepository()
    classifier = SummaryWritingEventClassifier(
        classifier=DeterministicInsuranceClassifier(),
        summary_writer=FakeSummaryWriter(),
    )
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository([raw_item]),
        external_event_repository=event_repo,
        classifier=classifier,
    )

    result = service.process_batch(limit=10, source_id="asf_ro")

    assert result.events_created == 1
    assert event_repo.events[0].title.startswith("AI headline")
    assert event_repo.events[0].classification_json is not None
    assert event_repo.events[0].classification_json.display_title.startswith("AI headline")


def test_process_batch_replaces_generic_source_label_with_event_headline() -> None:
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000017"),
        "Meteo Romania | Avertizari Nowcasting",
        "Avertizare cod galben pentru furtuni, vijelie, ploi si grindina.",
    )
    event_repo = FakeExternalEventRepository()
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository([raw_item]),
        external_event_repository=event_repo,
        classifier=DeterministicInsuranceClassifier(),
    )

    result = service.process_batch(limit=10, source_id="asf_ro")

    assert result.events_created == 1
    assert event_repo.events[0].title == (
        "Storm and hail warning issued for Romanian property exposure review"
    )


def test_process_batch_stores_classified_and_suppressed_events() -> None:
    relevant = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000004"),
        "ASF comunicare PAD",
        "Asigurari de locuinte PAD si cutremur.",
    )
    suppressed = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000005"),
        "ASF comunicare pensii",
        "Pensii private si fonduri.",
    )
    event_repo = FakeExternalEventRepository()
    audit_repo = FakeAuditRepository()
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository([relevant, suppressed]),
        external_event_repository=event_repo,
        classifier=DeterministicInsuranceClassifier(),
        audit_repository=audit_repo,
    )

    result = service.process_batch(limit=10, source_id="asf_ro")

    assert result.status == "success"
    assert result.raw_items_seen == 2
    assert result.events_created == 2
    assert result.classified == 1
    assert result.suppressed == 1
    assert result.failed == 0
    assert [event.status for event in event_repo.events] == ["classified", "suppressed"]
    assert len(audit_repo.records) == 2


def test_fallback_classifier_uses_deterministic_classifier_when_ai_fails() -> None:
    raw_item = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000009"),
        "ASF comunicare PAD",
        "Asigurari de locuinte PAD si cutremur.",
    )
    event_repo = FakeExternalEventRepository()
    audit_repo = FakeAuditRepository()
    classifier = FallbackEventClassifier(
        primary=FailingClassifier(),
        fallback=DeterministicInsuranceClassifier(),
    )
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository([raw_item]),
        external_event_repository=event_repo,
        classifier=classifier,
        audit_repository=audit_repo,
    )

    result = service.process_batch(limit=10)

    assert result.events_created == 1
    assert result.failed == 0
    assert event_repo.events[0].status == "classified"
    assert audit_repo.records[0].model_name == "deterministic-keyword-classifier"
    assert "ai unavailable" in audit_repo.records[0].input_ref_json["classifier_error"]


def test_process_batch_continues_after_one_item_failure() -> None:
    failing = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000006"),
        "ASF comunicare PAD",
        "Asigurari de locuinte PAD.",
    )
    succeeding = make_raw_item(
        UUID("40000000-0000-0000-0000-000000000007"),
        "ASF comunicare cutremur",
        "Asigurari de locuinte si cutremur.",
    )
    event_repo = FakeExternalEventRepository(error_on_raw_item_id=failing.raw_item_id)
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository([failing, succeeding]),
        external_event_repository=event_repo,
        classifier=DeterministicInsuranceClassifier(),
    )

    result = service.process_batch(limit=10)

    assert result.status == "success"
    assert result.raw_items_seen == 2
    assert result.events_created == 1
    assert result.classified == 1
    assert result.failed == 1
    assert "event insert failed" in result.errors[0]


def test_process_batch_returns_failed_when_raw_query_fails() -> None:
    service = SourceItemProcessingService(
        source_repository=FakeSourceRepository({"asf_ro": make_source()}),
        raw_item_repository=FakeRawItemRepository(error=RuntimeError("db unavailable")),
        external_event_repository=FakeExternalEventRepository(),
        classifier=DeterministicInsuranceClassifier(),
    )

    result = service.process_batch(limit=10)

    assert result.status == "failed"
    assert result.raw_items_seen == 0
    assert result.errors == ["db unavailable"]
