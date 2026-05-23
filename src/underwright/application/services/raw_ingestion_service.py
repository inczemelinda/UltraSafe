from __future__ import annotations

from typing import Any

from underwright.domain.intelligence import IngestionRun


class RawIngestionService:
    def __init__(
        self,
        source_repository,
        raw_item_repository,
        ingestion_run_repository,
        connector_registry: dict[str, Any],
    ) -> None:
        self.source_repository = source_repository
        self.raw_item_repository = raw_item_repository
        self.ingestion_run_repository = ingestion_run_repository
        self.connector_registry = connector_registry

    def run_once(self, source_id: str, limit: int | None = None) -> IngestionRun:
        run = self.ingestion_run_repository.start(source_id)

        try:
            source = self.source_repository.get_enabled(source_id)
            connector = self.connector_registry[source.connector_type]

            items = connector.fetch_items(source, limit=limit)

            created = 0
            for item in items:
                if self.raw_item_repository.save_if_new(item):
                    created += 1
            return self.ingestion_run_repository.finish(
                run=run,
                status="success",
                raw_items_seen=len(items),
                raw_items_created=created,
                errors=[],
            )

        except Exception as exc:
            return self.ingestion_run_repository.finish(
                run=run,
                status="failed",
                raw_items_seen=0,
                raw_items_created=0,
                errors=[str(exc)],
            )

    def preview(self, source_id: str, limit: int = 10) -> list[Any]:
        source = self.source_repository.get_enabled(source_id)
        connector = self.connector_registry[source.connector_type]
        if not hasattr(connector, "preview_items"):
            raise ValueError(
                f"Connector does not support preview: {source.connector_type}"
            )
        return connector.preview_items(source, limit=limit)
