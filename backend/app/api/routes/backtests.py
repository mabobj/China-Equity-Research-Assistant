"""回测相关路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_backtest_service
from app.schemas.backtest import (
    BacktestRunResponse,
    ScreenerBacktestRunRequest,
    StrategyBacktestRunRequest,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/screener/run", response_model=BacktestRunResponse)
def run_screener_backtest(
    request: ScreenerBacktestRunRequest,
    service: Any = Depends(get_backtest_service),
) -> BacktestRunResponse:
    try:
        return service.run_screener_backtest(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/strategy/run", response_model=BacktestRunResponse)
def run_strategy_backtest(
    request: StrategyBacktestRunRequest,
    service: Any = Depends(get_backtest_service),
) -> BacktestRunResponse:
    try:
        return service.run_strategy_backtest(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

