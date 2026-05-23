from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from underwright.api.intelligence_dependencies import get_raw_ingestion_query_service
from underwright.api.main import create_app
from underwright.domain.intelligence import IngestionRun, RawSourceItem


RAW_ITEM_ID = UUID("40000000-0000-0000-0000-000000000001")


class FakeRawIngestionQueryService:
    def __init__(self) -> None:
        self.raw_items_limit = None
        self.raw_item_id = None
        self.runs_limit = None
        self.run_id = None
        self.raise_on_raw_item = False
        self.raise_on_run = False

    def list_raw_items(self, limit: int = 50):
        self.raw_items_limit = limit
        return [make_raw_item()]

    def get_raw_item(self, raw_item_id):
        self.raw_item_id = raw_item_id
        if self.raise_on_raw_item:
            raise ValueError("RawSourceItem not found")
        return make_raw_item()

    def list_ingestion_runs(self, limit: int = 50):
        self.runs_limit = limit
        return [make_ingestion_run()]

    def get_ingestion_run(self, run_id):
        self.run_id = run_id
        if self.raise_on_run:
            raise ValueError("IngestionRun not found")
        return make_ingestion_run(run_id)


def make_raw_item() -> RawSourceItem:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=UTC)
    return RawSourceItem(
        raw_item_id=RAW_ITEM_ID,
        source_id="asf_ro",
        original_url="https://asfromania.ro/item",
        canonical_url="https://asfromania.ro/item",
        fetched_at=now,
        title="ASF comunicare",
        extracted_text="Text despre asigurari de locuinte.",
        content_hash="hash-1",
        created_at=now,
    )


def make_ingestion_run(run_id=None) -> IngestionRun:
    return IngestionRun(
        run_id=run_id or uuid4(),
        source_id="asf_ro",
        status="success",
        raw_items_seen=3,
        raw_items_created=2,
        started_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 7, 9, 1, tzinfo=UTC),
    )


def make_client(service: FakeRawIngestionQueryService):
    app = create_app()
    app.dependency_overrides[get_raw_ingestion_query_service] = lambda: service
    return TestClient(app)


def test_list_raw_items_route_uses_query_service() -> None:
    service = FakeRawIngestionQueryService()
    client = make_client(service)

    response = client.get("/intelligence/raw-items", params={"limit": 7})

    assert response.status_code == 200
    assert response.json()[0]["source_id"] == "asf_ro"
    assert service.raw_items_limit == 7


def test_get_raw_item_route_uses_query_service() -> None:
    service = FakeRawIngestionQueryService()
    client = make_client(service)

    response = client.get(f"/intelligence/raw-items/{RAW_ITEM_ID}")

    assert response.status_code == 200
    assert response.json()["raw_item_id"] == str(RAW_ITEM_ID)
    assert service.raw_item_id == RAW_ITEM_ID


def test_get_raw_item_route_returns_404_when_missing() -> None:
    service = FakeRawIngestionQueryService()
    service.raise_on_raw_item = True
    client = make_client(service)

    response = client.get(f"/intelligence/raw-items/{RAW_ITEM_ID}")

    assert response.status_code == 404
    assert "RawSourceItem not found" in response.json()["detail"]


def test_list_ingestion_runs_route_uses_query_service() -> None:
    service = FakeRawIngestionQueryService()
    client = make_client(service)

    response = client.get("/intelligence/ingestion-runs", params={"limit": 9})

    assert response.status_code == 200
    assert response.json()[0]["source_id"] == "asf_ro"
    assert service.runs_limit == 9


def test_get_ingestion_run_route_uses_query_service() -> None:
    service = FakeRawIngestionQueryService()
    client = make_client(service)
    run_id = uuid4()

    response = client.get(f"/intelligence/ingestion-runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["run_id"] == str(run_id)
    assert service.run_id == run_id


def test_get_ingestion_run_route_returns_404_when_missing() -> None:
    service = FakeRawIngestionQueryService()
    service.raise_on_run = True
    client = make_client(service)

    response = client.get(f"/intelligence/ingestion-runs/{uuid4()}")

    assert response.status_code == 404
    assert "IngestionRun not found" in response.json()["detail"]
