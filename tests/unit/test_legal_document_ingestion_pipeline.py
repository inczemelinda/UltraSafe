from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
from pathlib import Path
from uuid import UUID

import httpx

from underwright.api.routes.intelligence import (
    list_legal_template_review_candidates,
)
from underwright.application.services import (
    legal_document_template_correlation_service as legal_template_correlation,
)
from underwright.application.services.legal_document_normalization_service import (
    LegalDocumentNormalizationService,
)
from underwright.application.services.legal_review_wording_impact_service import (
    LegalReviewWordingImpactService,
)
from underwright.application.services.raw_ingestion_service import RawIngestionService
from underwright.application.services.source_item_processing_service import (
    DeterministicInsuranceClassifier,
    SourceItemProcessingService,
)
from underwright.domain.intelligence import (
    ExternalEvent,
    IngestionRun,
    RawSourceItem,
    Source,
)
from underwright.domain.legal_intelligence import (
    LegalDocumentTemplateReviewCandidate,
    LegalDocumentTemplateReviewItem,
    LegalDocumentNormalizationResult,
    NormalizedLegalDocument,
)
from underwright.domain.models import Template
from underwright.domain.wording import WordingDocument, WordingDocumentVersion
from underwright.infrastructure.legal_document_parsers import (
    build_legal_document_parser_registry,
)
from underwright.infrastructure.source_connectors.configured_web import (
    ConfiguredWebSourceConnector,
)
from underwright.infrastructure.source_connectors.legislatie_just import (
    build_raw_source_item_from_detail_html,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/legal_documents"
LEGISLATIE_FIXTURES = ROOT / "tests/fixtures/legislatie_just"
NOW = datetime(2026, 5, 11, 10, 0, tzinfo=UTC)


class InMemorySourceRepository:
    def __init__(self, sources: list[Source]) -> None:
        self.sources = {source.source_id: source for source in sources}

    def get_by_id(self, source_id: str) -> Source:
        return self.sources[source_id]

    def get_enabled(self, source_id: str) -> Source:
        source = self.sources[source_id]
        if not source.enabled:
            raise ValueError(f"Source is disabled: {source_id}")
        return source


class InMemoryLegalDocumentRepository:
    def __init__(
        self,
        *,
        sources: InMemorySourceRepository,
        raw_items: list[RawSourceItem],
    ) -> None:
        self.sources = sources
        self.raw_items = list(raw_items)
        self.documents: list[NormalizedLegalDocument] = []
        self.results: dict[UUID, LegalDocumentNormalizationResult] = {}
        self.external_event_rows: list[object] = []

    def list_pending_legal_raw_items(
        self,
        limit: int = 50,
        source_id: str | None = None,
    ) -> list[RawSourceItem]:
        pending_items = []
        for raw_item in self.raw_items:
            source = self.sources.get_by_id(raw_item.source_id)
            if source.config_json.get("pipeline_domain") != "legal_documents":
                continue
            if source_id is not None and raw_item.source_id != source_id:
                continue
            if raw_item.raw_item_id in self.results:
                continue
            if self.find_by_raw_source_item_id(raw_item.raw_item_id) is not None:
                continue
            pending_items.append(raw_item)
        return pending_items[:limit]

    def list_for_template_correlation(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> list[NormalizedLegalDocument]:
        documents = [
            document
            for document in self.documents
            if source_id is None or document.source_id == source_id
        ]
        return documents[:limit]

    def save(self, document: NormalizedLegalDocument) -> NormalizedLegalDocument:
        existing = self.find_by_raw_source_item_id(document.raw_source_item_id)
        if existing is not None:
            return existing

        for candidate in self.documents:
            if (
                document.external_identifier
                and candidate.source_id == document.source_id
                and candidate.external_identifier == document.external_identifier
            ):
                return candidate
            if (
                candidate.source_id == document.source_id
                and candidate.canonical_url == document.canonical_url
            ):
                return candidate
            if (
                candidate.source_id == document.source_id
                and candidate.document_hash == document.document_hash
            ):
                return candidate

        self.documents.append(document)
        return document

    def find_by_raw_source_item_id(
        self,
        raw_source_item_id: UUID,
    ) -> NormalizedLegalDocument | None:
        for document in self.documents:
            if document.raw_source_item_id == raw_source_item_id:
                return document
        return None

    def save_normalization_result(
        self,
        result: LegalDocumentNormalizationResult,
    ) -> LegalDocumentNormalizationResult:
        self.results[result.raw_source_item_id] = result
        return result


class InMemoryRawSourceItemRepository:
    def __init__(self) -> None:
        self.items: list[RawSourceItem] = []
        self.keys: set[tuple[str, str, str]] = set()

    def save_if_new(self, item: RawSourceItem) -> bool:
        key = (item.source_id, item.canonical_url, item.content_hash)
        if key in self.keys:
            return False
        self.keys.add(key)
        self.items.append(item)
        return True

    def list_unprocessed(
        self,
        limit: int,
        source_id: str | None = None,
    ) -> list[RawSourceItem]:
        items = [
            item
            for item in self.items
            if source_id is None or item.source_id == source_id
        ]
        return items[:limit]


class InMemoryIngestionRunRepository:
    def __init__(self) -> None:
        self.runs: list[IngestionRun] = []

    def start(self, source_id: str) -> IngestionRun:
        run = IngestionRun(
            source_id=source_id,
            status="started",
            started_at=NOW,
        )
        self.runs.append(run)
        return run

    def finish(
        self,
        *,
        run: IngestionRun,
        status: str,
        raw_items_seen: int,
        raw_items_created: int,
        errors: list[str],
    ) -> IngestionRun:
        finished = run.model_copy(
            update={
                "status": status,
                "raw_items_seen": raw_items_seen,
                "raw_items_created": raw_items_created,
                "errors": errors,
                "finished_at": NOW,
            }
        )
        self.runs[-1] = finished
        return finished


class InMemoryExternalEventRepository:
    def __init__(self) -> None:
        self.events: list[ExternalEvent] = []
        self.raw_item_ids: set[UUID] = set()

    def save_if_new(self, event: ExternalEvent) -> bool:
        if event.raw_item_id in self.raw_item_ids:
            return False
        self.raw_item_ids.add(event.raw_item_id)
        self.events.append(event)
        return True


class InMemoryTemplateRepository:
    def __init__(self, templates: list[Template]) -> None:
        self.templates = templates

    def list_active(self) -> list[Template]:
        return self.templates


class InMemoryLegalTemplateCandidateRepository:
    def __init__(
        self,
        legal_document_repository: InMemoryLegalDocumentRepository,
    ) -> None:
        self.legal_document_repository = legal_document_repository
        self.candidates: list[LegalDocumentTemplateReviewCandidate] = []
        self.keys: set[tuple[UUID, int, str, str, str | None]] = set()

    def save_if_new(
        self,
        candidate: LegalDocumentTemplateReviewCandidate,
    ) -> bool:
        key = (
            candidate.normalized_legal_document_id,
            candidate.template_id,
            candidate.template_version_hash,
            candidate.match_type,
            candidate.matched_reference,
        )
        if key in self.keys:
            return False
        self.keys.add(key)
        self.candidates.append(candidate)
        return True

    def list_review_items(
        self,
        status: str | None = "needs_review",
        limit: int = 50,
    ) -> list[LegalDocumentTemplateReviewItem]:
        items: list[LegalDocumentTemplateReviewItem] = []
        for document in self.legal_document_repository.documents:
            candidates = [
                candidate
                for candidate in self.candidates
                if candidate.normalized_legal_document_id == document.id
                and (status is None or candidate.status == status)
            ]
            if not candidates:
                continue
            highest_confidence = max(candidate.confidence for candidate in candidates)
            items.append(
                LegalDocumentTemplateReviewItem(
                    legal_document=document,
                    candidates=candidates,
                    affected_template_count=len(candidates),
                    highest_confidence=highest_confidence,
                )
            )
        return items[:limit]


class FakeWordingDocumentService:
    def __init__(
        self,
        documents: list[WordingDocument],
        current_versions: dict[int, WordingDocumentVersion],
    ) -> None:
        self.documents = documents
        self.current_versions = current_versions
        self.publish_calls = []
        self.update_calls = []

    def list_wording_documents(self) -> list[WordingDocument]:
        return self.documents

    def get_current_published_version(
        self,
        wording_document_id: int,
    ) -> WordingDocumentVersion:
        return self.current_versions[wording_document_id]

    def publish_wording_version(self, *args, **kwargs):
        self.publish_calls.append((args, kwargs))
        raise AssertionError("Pipeline must not publish wording versions.")

    def update_wording_version_full_text(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))
        raise AssertionError("Pipeline must not mutate wording text.")


class EmptyPolicyWordingService:
    def get_relevant_wording_sections(self, *args, **kwargs):
        return []


def test_legislatie_pipeline_reaches_api_wording_impacts() -> None:
    source = _legislatie_pipeline_source()
    source_repository = InMemorySourceRepository([source])
    raw_item_repository = InMemoryRawSourceItemRepository()
    ingestion_run_repository = InMemoryIngestionRunRepository()
    http_client = httpx.Client(
        transport=httpx.MockTransport(_legislatie_pipeline_http_handler)
    )
    ingestion_service = RawIngestionService(
        source_repository=source_repository,
        raw_item_repository=raw_item_repository,
        ingestion_run_repository=ingestion_run_repository,
        connector_registry={
            "web_scrape": ConfiguredWebSourceConnector(http_client),
        },
    )

    ingestion_run = ingestion_service.run_once("ro_portal_legislativ")

    assert ingestion_run.status == "success"
    assert ingestion_run.raw_items_seen == 1
    assert ingestion_run.raw_items_created == 1
    raw_item = raw_item_repository.items[0]
    assert raw_item.source_id == "ro_portal_legislativ"
    assert raw_item.canonical_url == (
        "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
    )
    assert raw_item.metadata_json["extractor_id"] == "legislatie_just"
    assert "Articolul 1" in raw_item.extracted_text
    assert "asigurarea obligatorie a locuințelor" in raw_item.extracted_text
    assert "<html" not in raw_item.extracted_text.lower()

    legal_document_repository = InMemoryLegalDocumentRepository(
        sources=source_repository,
        raw_items=raw_item_repository.items,
    )
    normalization_service = LegalDocumentNormalizationService(
        source_repository=source_repository,
        legal_document_repository=legal_document_repository,
        parser_registry=build_legal_document_parser_registry(),
    )

    normalization_result = normalization_service.process_pending(
        limit=20,
        source_id="ro_portal_legislativ",
    )

    assert normalization_result.status == "success"
    assert normalization_result.normalized == 1
    legal_document = legal_document_repository.documents[0]
    assert legal_document.source_id == "ro_portal_legislativ"
    assert legal_document.parser_id == "ro_portal_legislativ"
    assert legal_document.source_metadata["extractor_id"] == "legislatie_just"
    assert legal_document.source_metadata["synthetic"] is False
    assert legal_document.instrument_type == "lege"
    assert legal_document.instrument_number == "120"
    assert legal_document.instrument_year == 2026
    assert _canonical_references(legal_document.amends) == {"ro:lege:260:2008"}
    assert [clause["clause_id"] for clause in legal_document.structured_clauses] == [
        "Articolul 1",
        "Articolul 2",
    ]

    external_event_repository = InMemoryExternalEventRepository()
    processing_service = SourceItemProcessingService(
        source_repository=source_repository,
        raw_item_repository=raw_item_repository,
        external_event_repository=external_event_repository,
        classifier=DeterministicInsuranceClassifier(),
    )

    processing_result = processing_service.process_batch(
        limit=20,
        source_id="ro_portal_legislativ",
    )

    assert processing_result.status == "success"
    assert processing_result.classified == 1
    event = external_event_repository.events[0]
    assert event.status == "classified"
    assert event.line_of_business == "property"
    assert "PAD / compulsory home insurance" in event.topics_json
    assert "coverage wording" in event.topics_json

    template = _pipeline_template()
    original_template_content = template.content
    candidate_repository = InMemoryLegalTemplateCandidateRepository(
        legal_document_repository,
    )
    correlation_service = (
        legal_template_correlation.LegalDocumentTemplateCorrelationService(
            legal_document_repository=legal_document_repository,
            template_repository=InMemoryTemplateRepository([template]),
            candidate_repository=candidate_repository,
        )
    )

    correlation_result = correlation_service.correlate_batch(
        limit=20,
        source_id="ro_portal_legislativ",
    )

    assert correlation_result.status == "success"
    assert correlation_result.candidates_created >= 1
    candidate = next(
        candidate
        for candidate in candidate_repository.candidates
        if candidate.match_type == "amended_reference"
    )
    assert candidate.template_code == "PAD_PROPERTY_WORDING_RO"
    assert candidate.matched_reference == "ro:lege:260:2008"
    assert candidate.status == "needs_review"

    wording_service = FakeWordingDocumentService(
        [_pipeline_wording_document()],
        {501: _pipeline_wording_version()},
    )
    response_items = list_legal_template_review_candidates(
        repository=candidate_repository,
        wording_impact_service=LegalReviewWordingImpactService(
            wording_service,
            policy_wording_service=EmptyPolicyWordingService(),
        ),
    )

    body = [item.model_dump(mode="json") for item in response_items]
    assert body[0]["legal_document"]["source_metadata"]["synthetic"] is False
    impact = body[0]["wording_document_impacts"][0]
    assert impact["wording_document_code"] == "PAD_PROPERTY_WORDING_RO"
    assert impact["current_published_version_id"] == 9001
    assert impact["affected_legal_references"] == ["ro:lege:260:2008"]
    assert impact["affected_clause_ids"] == ["claims.notification"]
    assert impact["matched_text_snippets"]
    assert "10 zile calendaristice" in impact["proposed_changes"][0]["current_text"]
    assert "5 zile calendaristice" in impact["proposed_changes"][0]["proposed_text"]
    assert impact["safe_to_auto_draft"] is False
    assert template.content == original_template_content
    assert wording_service.publish_calls == []
    assert wording_service.update_calls == []


def test_fixture_based_legal_document_ingestion_pipeline() -> None:
    source_repository = InMemorySourceRepository(
        [
            _legal_source(
                source_id="ro_portal_legislativ",
                country="RO",
                source_type="legal_portal",
                language="ro",
                parser_id="ro_portal_legislativ",
            ),
            _legal_source(
                source_id="eu_eurlex_oj_l_series",
                country="EU",
                source_type="official_journal",
                language="en",
                parser_id="eu_eurlex_oj",
            ),
        ]
    )
    raw_items = [
        _raw_item(
            raw_item_id=UUID("51000000-0000-0000-0000-000000000001"),
            source_id="ro_portal_legislativ",
            title="DEMO - Legea nr. 99/2026 pentru modificarea Legii nr. 260/2008",
            fixture_name="ro_lege_99_2026.txt",
            url="https://legislatie.just.ro/Public/DetaliiDocument/990026",
        ),
        _raw_item(
            raw_item_id=UUID("51000000-0000-0000-0000-000000000002"),
            source_id="eu_eurlex_oj_l_series",
            title="DEMO - Regulation (EU) 2026/432",
            fixture_name="eu_regulation_2026_432.txt",
            url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L:2026:432",
        ),
        _raw_item(
            raw_item_id=UUID("51000000-0000-0000-0000-000000000003"),
            source_id="ro_portal_legislativ",
            title="DEMO - ASF insurance supervision conference",
            fixture_name="noisy_regulator_conference.txt",
            url="https://legislatie.just.ro/Public/News/conference",
        ),
    ]
    legal_document_repository = InMemoryLegalDocumentRepository(
        sources=source_repository,
        raw_items=raw_items,
    )
    service = LegalDocumentNormalizationService(
        source_repository=source_repository,
        legal_document_repository=legal_document_repository,
        parser_registry=build_legal_document_parser_registry(),
    )

    first_run = service.process_pending(limit=10)
    second_run = service.process_pending(limit=10)

    assert first_run.status == "success"
    assert first_run.raw_items_seen == 3
    assert first_run.normalized == 2
    assert first_run.suppressed == 1
    assert second_run.raw_items_seen == 0
    assert len(legal_document_repository.documents) == 2
    assert len(legal_document_repository.results) == 3
    assert legal_document_repository.external_event_rows == []

    ro_document = legal_document_repository.find_by_raw_source_item_id(
        UUID("51000000-0000-0000-0000-000000000001")
    )
    assert ro_document is not None
    assert ro_document.jurisdiction == "RO"
    assert ro_document.instrument_type == "lege"
    assert ro_document.instrument_number == "99"
    assert ro_document.instrument_year == 2026
    assert _canonical_references(ro_document.legal_references) >= {
        "ro:lege:99:2026",
        "ro:lege:260:2008",
    }
    assert _canonical_references(ro_document.amends) == {"ro:lege:260:2008"}
    assert "Monitorul Oficial" in (ro_document.publication_reference or "")
    assert ro_document.effective_date.isoformat() == "2026-06-15"
    assert ro_document.extraction_confidence >= 0.8
    assert ro_document.source_metadata["synthetic"] is True
    assert legal_document_repository.results[ro_document.raw_source_item_id].status == (
        "normalized"
    )

    eu_document = legal_document_repository.find_by_raw_source_item_id(
        UUID("51000000-0000-0000-0000-000000000002")
    )
    assert eu_document is not None
    assert eu_document.jurisdiction == "EU"
    assert eu_document.instrument_type == "regulation"
    assert eu_document.instrument_number == "432"
    assert eu_document.instrument_year == 2026
    assert _canonical_references(eu_document.legal_references) >= {
        "eu:regulation:2026:432",
        "eu:regulation:2024:100",
    }
    assert _canonical_references(eu_document.amends) == {"eu:regulation:2024:100"}
    assert eu_document.effective_date.isoformat() == "2026-08-01"
    assert eu_document.extraction_confidence >= 0.8
    assert eu_document.source_metadata["synthetic"] is True

    noisy_result = legal_document_repository.results[
        UUID("51000000-0000-0000-0000-000000000003")
    ]
    assert noisy_result.status == "suppressed_non_legislative"
    assert noisy_result.reason is not None
    assert "No supported legal act found" in noisy_result.reason
    assert (
        legal_document_repository.find_by_raw_source_item_id(
            noisy_result.raw_source_item_id
        )
        is None
    )


def test_legal_ingestion_pipeline_does_not_import_ai_or_external_events() -> None:
    checked_files = [
        "src/underwright/application/services/legal_document_normalization_service.py",
        "src/underwright/infrastructure/legal_document_parsers/deterministic.py",
        "src/underwright/infrastructure/legal_document_parsers/registry.py",
    ]
    blocked_patterns = (
        "underwright.infrastructure.llm",
        "intelligence_classifier",
        "OpenAI",
        "external_event",
        "ExternalEvent",
    )

    for relative_path in checked_files:
        source_text = (ROOT / relative_path).read_text()
        for blocked_pattern in blocked_patterns:
            assert blocked_pattern not in source_text


def test_legal_ingestion_pipeline_records_parser_failures() -> None:
    source_repository = InMemorySourceRepository(
        [
            _legal_source(
                source_id="ro_portal_legislativ",
                country="RO",
                source_type="legal_portal",
                language="ro",
                parser_id="missing_parser",
            )
        ]
    )
    raw_item = _raw_item(
        raw_item_id=UUID("51000000-0000-0000-0000-000000000004"),
        source_id="ro_portal_legislativ",
        title="DEMO - Legea nr. 99/2026",
        fixture_name="ro_lege_99_2026.txt",
        url="https://legislatie.just.ro/Public/DetaliiDocument/990026",
    )
    legal_document_repository = InMemoryLegalDocumentRepository(
        sources=source_repository,
        raw_items=[raw_item],
    )
    service = LegalDocumentNormalizationService(
        source_repository=source_repository,
        legal_document_repository=legal_document_repository,
        parser_registry=build_legal_document_parser_registry(),
    )

    result = service.process_pending(limit=10)

    assert result.status == "failed"
    assert result.failed == 1
    assert len(legal_document_repository.documents) == 0
    saved_result = legal_document_repository.results[raw_item.raw_item_id]
    assert saved_result.status == "parser_failed"
    assert saved_result.parser_id == "missing_parser"
    assert "Unknown legal document parser_id" in (saved_result.reason or "")


def test_legislatie_raw_item_normalizes_with_metadata_and_articles() -> None:
    source_repository = InMemorySourceRepository(
        [
            _legal_source(
                source_id="ro_portal_legislativ",
                country="RO",
                source_type="legal_portal",
                language="ro",
                parser_id="ro_portal_legislativ",
            )
        ]
    )
    raw_item = _legislatie_raw_item(
        raw_item_id=UUID("51000000-0000-0000-0000-000000000005")
    )
    legal_document_repository = InMemoryLegalDocumentRepository(
        sources=source_repository,
        raw_items=[raw_item],
    )
    service = LegalDocumentNormalizationService(
        source_repository=source_repository,
        legal_document_repository=legal_document_repository,
        parser_registry=build_legal_document_parser_registry(),
    )

    result = service.process_pending(limit=10)

    assert result.status == "success"
    assert result.normalized == 1
    document = legal_document_repository.documents[0]
    assert document.raw_source_item_id == raw_item.raw_item_id
    assert document.source_url == raw_item.original_url
    assert document.title.startswith("DECIZIE nr. 1.074 din 4 septembrie 2018")
    assert document.instrument_type == "decizie"
    assert document.instrument_number == "1074"
    assert document.instrument_year == 2018
    assert document.instrument_date == date(2018, 9, 4)
    assert document.issuer == "CURTEA CONSTITUȚIONALĂ"
    assert document.publication_reference == (
        "Publicat în MONITORUL OFICIAL nr. 144 din 22 februarie 2019"
    )
    assert document.publication_date == date(2019, 2, 22)
    assert document.effective_date == date(2019, 2, 22)
    assert document.jurisdiction == "RO"
    assert document.language == "ro"
    assert document.status == "in_force"
    assert _canonical_references(document.legal_references) >= {
        "ro:decizie:1074:2018",
        "ro:lege:47:1992",
    }
    assert [clause["clause_id"] for clause in document.structured_clauses] == [
        "Articolul 1",
        "Articolul 2",
    ]
    assert [clause["order"] for clause in document.structured_clauses] == [1, 2]
    assert "neconstituționalitate" in document.structured_clauses[0]["text"]
    assert "României" in document.structured_clauses[1]["text"]
    assert "<html" not in document.full_text.lower()
    assert "Print" not in document.full_text
    assert "Articolul 1" in document.full_text
    assert document.document_hash == _normalized_text_hash(document.full_text)
    assert document.document_hash != hashlib.sha256(
        (raw_item.raw_html or "").encode("utf-8")
    ).hexdigest()
    assert document.source_metadata["source_item_id"] == str(raw_item.raw_item_id)
    assert document.source_metadata["structured_clause_count"] == 2


def test_legislatie_duplicate_raw_items_do_not_create_duplicate_documents() -> None:
    source_repository = InMemorySourceRepository(
        [
            _legal_source(
                source_id="ro_portal_legislativ",
                country="RO",
                source_type="legal_portal",
                language="ro",
                parser_id="ro_portal_legislativ",
            )
        ]
    )
    first_item = _legislatie_raw_item(
        raw_item_id=UUID("51000000-0000-0000-0000-000000000006")
    )
    duplicate_item = first_item.model_copy(
        update={
            "raw_item_id": UUID("51000000-0000-0000-0000-000000000007"),
            "fetched_at": datetime(2026, 5, 11, 10, 5, tzinfo=UTC),
            "created_at": datetime(2026, 5, 11, 10, 5, tzinfo=UTC),
        }
    )
    legal_document_repository = InMemoryLegalDocumentRepository(
        sources=source_repository,
        raw_items=[first_item, duplicate_item],
    )
    service = LegalDocumentNormalizationService(
        source_repository=source_repository,
        legal_document_repository=legal_document_repository,
        parser_registry=build_legal_document_parser_registry(),
    )

    result = service.process_pending(limit=10)

    assert result.status == "success"
    assert result.normalized == 1
    assert result.duplicate_unchanged == 1
    assert len(legal_document_repository.documents) == 1
    assert legal_document_repository.results[first_item.raw_item_id].status == (
        "normalized"
    )
    assert legal_document_repository.results[duplicate_item.raw_item_id].status == (
        "duplicate_unchanged"
    )


def _legislatie_pipeline_http_handler(request: httpx.Request) -> httpx.Response:
    if str(request.url) == "https://legislatie.just.ro/list":
        return httpx.Response(
            200,
            text=(LEGISLATIE_FIXTURES / "listing_lege_120_pad.html").read_text(
                encoding="utf-8"
            ),
        )
    if str(request.url) == (
        "https://legislatie.just.ro/Public/DetaliiDocument/1202026"
    ):
        return httpx.Response(
            200,
            text=(LEGISLATIE_FIXTURES / "detail_lege_120_pad.html").read_text(
                encoding="utf-8"
            ),
        )
    return httpx.Response(404, text="Not found")


def _legislatie_pipeline_source() -> Source:
    return Source(
        source_id="ro_portal_legislativ",
        name="Portal Legislativ Romania",
        country="RO",
        source_type="legal_portal",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        config_json={
            "pipeline_domain": "legal_documents",
            "parser_id": "ro_portal_legislativ",
            "extractor_id": "legislatie_just",
            "list_url": "https://legislatie.just.ro/list",
            "allowed_detail_hosts": ["legislatie.just.ro"],
            "allowed_path_fragments": ["/public/detaliidocument"],
            "allowed_url_patterns": [
                r"^https://legislatie\.just\.ro/(public|Public)/DetaliiDocument/\d+"
            ],
            "max_items": 20,
        },
        created_at=NOW,
        updated_at=NOW,
    )


def _pipeline_template() -> Template:
    return Template(
        id=501,
        template_code="PAD_PROPERTY_WORDING_RO",
        name="PAD Property Wording Romania",
        version="2026.1",
        document_type="insurance_contract",
        is_active=True,
        content=(
            "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
            "Asiguratul trebuie să notifice dauna în termen de 10 zile "
            "calendaristice."
        ),
        jurisdiction="RO",
        product_line="property",
        legal_references_json=["ro:lege:260:2008"],
        metadata_json={},
        created_at=NOW,
    )


def _pipeline_wording_document() -> WordingDocument:
    return WordingDocument(
        id=501,
        code="PAD_PROPERTY_WORDING_RO",
        title="PAD Property Wording Romania",
        product_line="property",
        jurisdiction="RO",
        language="ro",
        status="published",
        created_at=NOW,
        updated_at=NOW,
    )


def _pipeline_wording_version() -> WordingDocumentVersion:
    return WordingDocumentVersion(
        id=9001,
        wording_document_id=501,
        version="2026.1",
        status="published",
        full_text=(
            "Prezenta poliță este emisă în conformitate cu Legea nr. 260/2008. "
            "Asiguratul trebuie să notifice dauna în termen de 10 zile "
            "calendaristice."
        ),
        content_hash="published-wording-hash",
        legal_references_json=["ro:lege:260:2008"],
        structured_clauses_json=[
            {
                "id": "claims.notification",
                "title": "Notificarea daunelor",
                "text": (
                    "Asiguratul trebuie să notifice dauna în termen de 10 zile "
                    "calendaristice."
                ),
                "legal_references": ["ro:lege:260:2008"],
            }
        ],
        effective_from=date(2026, 1, 1),
        created_at=NOW,
        updated_at=NOW,
    )


def _legal_source(
    *,
    source_id: str,
    country: str,
    source_type: str,
    language: str,
    parser_id: str,
) -> Source:
    return Source(
        source_id=source_id,
        name=source_id,
        country=country,
        source_type=source_type,
        trust_tier="authoritative",
        connector_type="web_scrape",
        language=language,
        enabled=False,
        config_json={
            "pipeline_domain": "legal_documents",
            "parser_id": parser_id,
            "jurisdiction": country,
        },
        created_at=NOW,
        updated_at=NOW,
    )


def _raw_item(
    *,
    raw_item_id: UUID,
    source_id: str,
    title: str,
    fixture_name: str,
    url: str,
) -> RawSourceItem:
    text = (FIXTURES / fixture_name).read_text()
    return RawSourceItem(
        raw_item_id=raw_item_id,
        source_id=source_id,
        original_url=url,
        canonical_url=url,
        published_at=NOW,
        fetched_at=NOW,
        title=title,
        raw_html=f"<html><body><pre>{text}</pre></body></html>",
        extracted_text=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        created_at=NOW,
    )


def _canonical_references(values: list[dict[str, str]]) -> set[str]:
    return {value["canonical"] for value in values}


def _legislatie_raw_item(*, raw_item_id: UUID) -> RawSourceItem:
    item = build_raw_source_item_from_detail_html(
        source_id="ro_portal_legislativ",
        url="https://legislatie.just.ro/Public/DetaliiDocument/207887",
        html=(LEGISLATIE_FIXTURES / "detail_decizie_1074.html").read_text(
            encoding="utf-8"
        ),
        fetched_at=NOW,
    )
    return item.model_copy(update={"raw_item_id": raw_item_id, "created_at": NOW})


def _normalized_text_hash(text: str) -> str:
    normalized_text = "\n".join(line.strip() for line in text.splitlines())
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
