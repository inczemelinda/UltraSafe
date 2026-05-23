from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from underwright.api.intelligence_dependencies import get_raw_ingestion_query_service
from underwright.application.services.raw_ingestion_query_service import (
    RawIngestionQueryService,
)
from underwright.domain.intelligence import IngestionRun, RawSourceItem

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/raw-items", response_model=list[RawSourceItem])
def list_raw_items(
    limit: int = 50,
    service: RawIngestionQueryService = Depends(get_raw_ingestion_query_service),
) -> list[RawSourceItem]:
    return service.list_raw_items(limit)


@router.get("/raw-items/{raw_item_id}", response_model=RawSourceItem)
def get_raw_item(
    raw_item_id: UUID,
    service: RawIngestionQueryService = Depends(get_raw_ingestion_query_service),
) -> RawSourceItem:
    try:
        return service.get_raw_item(raw_item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/ingestion-runs", response_model=list[IngestionRun])
def list_ingestion_runs(
    limit: int = 50,
    service: RawIngestionQueryService = Depends(get_raw_ingestion_query_service),
) -> list[IngestionRun]:
    return service.list_ingestion_runs(limit)


@router.get("/ingestion-runs/{run_id}", response_model=IngestionRun)
def get_ingestion_run(
    run_id: UUID,
    service: RawIngestionQueryService = Depends(get_raw_ingestion_query_service),
) -> IngestionRun:
    try:
        return service.get_ingestion_run(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
