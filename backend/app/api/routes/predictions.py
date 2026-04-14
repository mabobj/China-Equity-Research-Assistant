"""预测相关路由。"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_prediction_service
from app.schemas.prediction import (
    CrossSectionPredictionRunRequest,
    CrossSectionPredictionRunResponse,
    PredictionSnapshotResponse,
)
from app.schemas.lineage import LineageMetadata

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/{symbol}", response_model=PredictionSnapshotResponse)
def get_symbol_prediction(
    symbol: str,
    as_of_date: Optional[date] = Query(default=None),
    model_version: Optional[str] = Query(default=None),
    service: Any = Depends(get_prediction_service),
) -> PredictionSnapshotResponse:
    try:
        return service.get_symbol_prediction(
            symbol=symbol,
            as_of_date=as_of_date,
            model_version=model_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{symbol}/lineage", response_model=LineageMetadata)
def get_symbol_prediction_lineage(
    symbol: str,
    as_of_date: Optional[date] = Query(default=None),
    model_version: Optional[str] = Query(default=None),
    service: Any = Depends(get_prediction_service),
) -> LineageMetadata:
    try:
        response = service.get_symbol_prediction(
            symbol=symbol,
            as_of_date=as_of_date,
            model_version=model_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if response.lineage_metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"prediction lineage is unavailable: {symbol}",
        )
    return response.lineage_metadata


@router.post("/cross-section/run", response_model=CrossSectionPredictionRunResponse)
def run_cross_section_prediction(
    request: CrossSectionPredictionRunRequest,
    service: Any = Depends(get_prediction_service),
) -> CrossSectionPredictionRunResponse:
    try:
        return service.run_cross_section_prediction(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
