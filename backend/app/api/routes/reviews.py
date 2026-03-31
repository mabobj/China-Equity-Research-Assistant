"""复盘记录路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_review_record_service
from app.schemas.journal import (
    CreateReviewFromTradeRequest,
    CreateReviewRequest,
    ReviewListResponse,
    ReviewRecord,
    UpdateReviewRequest,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/from-trade/{trade_id}", response_model=ReviewRecord)
def create_review_from_trade(
    trade_id: str,
    request: CreateReviewFromTradeRequest,
    service: Any = Depends(get_review_record_service),
) -> ReviewRecord:
    try:
        return service.create_from_trade(trade_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Review service is temporarily unavailable.") from exc


@router.post("", response_model=ReviewRecord)
def create_review(
    request: CreateReviewRequest,
    service: Any = Depends(get_review_record_service),
) -> ReviewRecord:
    try:
        return service.create_review(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Review service is temporarily unavailable.") from exc


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    symbol: Optional[str] = Query(default=None),
    outcome_label: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    service: Any = Depends(get_review_record_service),
) -> ReviewListResponse:
    return service.list_reviews(symbol=symbol, outcome_label=outcome_label, limit=limit)


@router.get("/{review_id}", response_model=ReviewRecord)
def get_review(
    review_id: str,
    service: Any = Depends(get_review_record_service),
) -> ReviewRecord:
    record = service.get_review(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review record not found.")
    return record


@router.patch("/{review_id}", response_model=ReviewRecord)
def update_review(
    review_id: str,
    request: UpdateReviewRequest,
    service: Any = Depends(get_review_record_service),
) -> ReviewRecord:
    try:
        record = service.update_review(review_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Review record not found.")
    return record

