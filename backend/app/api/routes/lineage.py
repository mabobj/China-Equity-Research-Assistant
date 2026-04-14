"""Read-only lineage diagnostics routes."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_lineage_service
from app.schemas.lineage import LineageListResponse, LineageMetadata

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("/datasets", response_model=LineageListResponse)
def list_dataset_lineage(
    dataset: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    as_of_date: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: Any = Depends(get_lineage_service),
) -> LineageListResponse:
    return service.list_dataset_lineage(
        dataset=dataset,
        symbol=symbol,
        as_of_date=as_of_date,
        limit=limit,
    )


@router.get("/datasets/{dataset}/{dataset_version}", response_model=LineageMetadata)
def get_dataset_lineage(
    dataset: str,
    dataset_version: str,
    service: Any = Depends(get_lineage_service),
) -> LineageMetadata:
    try:
        return service.get_dataset_lineage(
            dataset=dataset,
            dataset_version=dataset_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
