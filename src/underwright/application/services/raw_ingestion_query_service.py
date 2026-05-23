from __future__ import annotations

from uuid import UUID


class RawIngestionQueryService:
    def __init__(
        self,
        raw_item_repository,
        ingestion_run_repository,
    ):
        self.raw_item_repository = raw_item_repository
        self.ingestion_run_repository = ingestion_run_repository

    def list_raw_items(self, limit: int = 50):
        return self.raw_item_repository.list_latest(limit)

    def get_raw_item(self, raw_item_id: UUID):
        return self.raw_item_repository.get_by_id(raw_item_id)

    def list_ingestion_runs(self, limit: int = 50):
        return self.ingestion_run_repository.list_latest(limit)

    def get_ingestion_run(self, run_id: UUID):
        return self.ingestion_run_repository.get_by_id(run_id)
