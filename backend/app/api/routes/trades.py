"""交易记录路由。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_trade_service
from app.schemas.journal import (
    CreateTradeFromCurrentDecisionRequest,
    CreateTradeRequest,
    TradeListResponse,
    TradeRecord,
    UpdateTradeRequest,
)

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/from-current-decision", response_model=TradeRecord)
def create_trade_from_current_decision(
    request: CreateTradeFromCurrentDecisionRequest,
    service: Any = Depends(get_trade_service),
) -> TradeRecord:
    try:
        return service.create_from_current_decision(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Trade service is temporarily unavailable.") from exc


@router.post("", response_model=TradeRecord)
def create_trade(
    request: CreateTradeRequest,
    service: Any = Depends(get_trade_service),
) -> TradeRecord:
    try:
        return service.create_trade(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Trade service is temporarily unavailable.") from exc


@router.get("", response_model=TradeListResponse)
def list_trades(
    symbol: Optional[str] = Query(default=None),
    side: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None, alias="from"),
    to_date: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=500),
    service: Any = Depends(get_trade_service),
) -> TradeListResponse:
    return service.list_trades(
        symbol=symbol,
        side=side,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/{trade_id}", response_model=TradeRecord)
def get_trade(
    trade_id: str,
    service: Any = Depends(get_trade_service),
) -> TradeRecord:
    record = service.get_trade(trade_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trade record not found.")
    return record


@router.patch("/{trade_id}", response_model=TradeRecord)
def update_trade(
    trade_id: str,
    request: UpdateTradeRequest,
    service: Any = Depends(get_trade_service),
) -> TradeRecord:
    try:
        record = service.update_trade(trade_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Trade record not found.")
    return record

