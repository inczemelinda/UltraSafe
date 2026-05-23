from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from underwright.application.services.raw_ingestion_service import RawIngestionService
from underwright.domain.intelligence import IngestionRun, RawSourceItem, Source


class FakeSourceRepository:
    def __init__(self, source: Source | None = None) -> None:
        self.source = source
        self.source_id = None

    def get_enabled(self, source_id: str) -> Source:
        self.source_id = source_id
        if self.source is None:
            raise ValueError("Source not found")
        return self.source


class FakeRawSourceItemRepository:
    def __init__(self, inserted_results: list[bool]) -> None:
        self.inserted_results = list(inserted_results)
        self.saved_items: list[RawSourceItem] = []

    def save_if_new(self, item: RawSourceItem) -> bool:
        self.saved_items.append(item)
        return self.inserted_results.pop(0)


class FakeIngestionRunRepository:
    def __init__(self) -> None:
        self.started_source_id = None
        self.finished = None

    def start(self, source_id: str) -> IngestionRun:
        self.started_source_id = source_id
        return IngestionRun(
            run_id=uuid4(),
            source_id=source_id,
            status="started",
            started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        )

    def finish(
        self,
        run: IngestionRun,
        status: str,
        raw_items_seen: int,
        raw_items_created: int,
        errors: list[str],
    ) -> IngestionRun:
        run.status = status
        run.raw_items_seen = raw_items_seen
        run.raw_items_created = raw_items_created
        run.errors = errors
        run.finished_at = datetime(2026, 5, 7, 9, 1, tzinfo=UTC)
        self.finished = run
        return run


class FakeConnector:
    def __init__(
        self,
        items: list[RawSourceItem] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.items = items or []
        self.error = error
        self.source = None
        self.limit = None
        self.preview_limit = None

    def fetch_items(
        self,
        source: Source,
        limit: int | None = None,
    ) -> list[RawSourceItem]:
        self.source = source
        self.limit = limit
        if self.error is not None:
            raise self.error
        return self.items

    def preview_items(self, source: Source, limit: int):
        self.source = source
        self.preview_limit = limit
        return ["preview"]


def make_source() -> Source:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return Source(
        source_id="asf_ro",
        name="ASF Romania",
        country="RO",
        source_type="regulator",
        trust_tier="authoritative",
        connector_type="web_scrape",
        language="ro",
        enabled=True,
        created_at=now,
        updated_at=now,
    )


def make_raw_item(url: str) -> RawSourceItem:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return RawSourceItem(
        source_id="asf_ro",
        original_url=url,
        canonical_url=url,
        fetched_at=now,
        title="ASF comunicare",
        extracted_text="Text despre asigurari de locuinte.",
        content_hash=url.rsplit("/", 1)[-1],
        created_at=now,
    )


def test_run_once_fetches_items_saves_new_rows_and_records_success() -> None:
    source = make_source()
    items = [
        make_raw_item("https://asfromania.ro/item-1"),
        make_raw_item("https://asfromania.ro/item-2"),
    ]
    raw_repo = FakeRawSourceItemRepository([True, False])
    run_repo = FakeIngestionRunRepository()
    connector = FakeConnector(items)
    service = RawIngestionService(
        source_repository=FakeSourceRepository(source),
        raw_item_repository=raw_repo,
        ingestion_run_repository=run_repo,
        connector_registry={"web_scrape": connector},
    )

    run = service.run_once("asf_ro")

    assert run.status == "success"
    assert run.raw_items_seen == 2
    assert run.raw_items_created == 1
    assert run.errors == []
    assert run_repo.started_source_id == "asf_ro"
    assert raw_repo.saved_items == items
    assert connector.source == source
    assert connector.limit is None


def test_run_once_passes_limit_to_connector() -> None:
    source = make_source()
    raw_repo = FakeRawSourceItemRepository([True])
    connector = FakeConnector([make_raw_item("https://asfromania.ro/item-1")])
    service = RawIngestionService(
        source_repository=FakeSourceRepository(source),
        raw_item_repository=raw_repo,
        ingestion_run_repository=FakeIngestionRunRepository(),
        connector_registry={"web_scrape": connector},
    )

    run = service.run_once("asf_ro", limit=7)

    assert run.status == "success"
    assert connector.limit == 7


def test_run_once_records_failure_when_source_lookup_fails() -> None:
    run_repo = FakeIngestionRunRepository()
    service = RawIngestionService(
        source_repository=FakeSourceRepository(None),
        raw_item_repository=FakeRawSourceItemRepository([]),
        ingestion_run_repository=run_repo,
        connector_registry={},
    )

    run = service.run_once("missing_source")

    assert run.status == "failed"
    assert run.raw_items_seen == 0
    assert run.raw_items_created == 0
    assert run.errors == ["Source not found"]


def test_run_once_records_failure_when_connector_fails() -> None:
    source = make_source()
    service = RawIngestionService(
        source_repository=FakeSourceRepository(source),
        raw_item_repository=FakeRawSourceItemRepository([]),
        ingestion_run_repository=FakeIngestionRunRepository(),
        connector_registry={
            "web_scrape": FakeConnector(error=RuntimeError("ASF unavailable"))
        },
    )

    run = service.run_once("asf_ro")

    assert run.status == "failed"
    assert run.errors == ["ASF unavailable"]


def test_preview_fetches_candidates_without_starting_run_or_saving() -> None:
    source = make_source()
    raw_repo = FakeRawSourceItemRepository([])
    run_repo = FakeIngestionRunRepository()
    connector = FakeConnector([])
    service = RawIngestionService(
        source_repository=FakeSourceRepository(source),
        raw_item_repository=raw_repo,
        ingestion_run_repository=run_repo,
        connector_registry={"web_scrape": connector},
    )

    preview = service.preview("asf_ro", limit=7)

    assert preview == ["preview"]
    assert connector.source == source
    assert connector.preview_limit == 7
    assert raw_repo.saved_items == []
    assert run_repo.started_source_id is None
