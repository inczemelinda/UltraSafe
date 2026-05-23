from __future__ import annotations

from uuid import uuid4

from underwright.application.services.raw_ingestion_query_service import (
    RawIngestionQueryService,
)


class FakeRawItemRepository:
    def __init__(self) -> None:
        self.limit = None
        self.raw_item_id = None

    def list_latest(self, limit: int = 50):
        self.limit = limit
        return ["raw-item"]

    def get_by_id(self, raw_item_id):
        self.raw_item_id = raw_item_id
        return "raw-item-detail"


class FakeIngestionRunRepository:
    def __init__(self) -> None:
        self.limit = None
        self.run_id = None

    def list_latest(self, limit: int = 50):
        self.limit = limit
        return ["run"]

    def get_by_id(self, run_id):
        self.run_id = run_id
        return "run-detail"


def test_query_service_delegates_raw_item_reads() -> None:
    raw_repo = FakeRawItemRepository()
    run_repo = FakeIngestionRunRepository()
    service = RawIngestionQueryService(raw_repo, run_repo)
    raw_item_id = uuid4()

    assert service.list_raw_items(limit=25) == ["raw-item"]
    assert service.get_raw_item(raw_item_id) == "raw-item-detail"
    assert raw_repo.limit == 25
    assert raw_repo.raw_item_id == raw_item_id


def test_query_service_delegates_ingestion_run_reads() -> None:
    raw_repo = FakeRawItemRepository()
    run_repo = FakeIngestionRunRepository()
    service = RawIngestionQueryService(raw_repo, run_repo)
    run_id = uuid4()

    assert service.list_ingestion_runs(limit=10) == ["run"]
    assert service.get_ingestion_run(run_id) == "run-detail"
    assert run_repo.limit == 10
    assert run_repo.run_id == run_id
