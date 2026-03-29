"""Structured strategy routes."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_strategy_plan_daily_dataset, get_strategy_planner
from app.schemas.strategy import StrategyPlan
from app.services.data_products.freshness import resolve_last_closed_trading_day

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/{symbol}", response_model=StrategyPlan)
def get_strategy_plan(
    symbol: str,
    force_refresh: bool = Query(default=False),
    planner: Any = Depends(get_strategy_planner),
    strategy_plan_daily: Any = Depends(get_strategy_plan_daily_dataset),
) -> StrategyPlan:
    """Return the structured strategy plan."""

    as_of_date = resolve_last_closed_trading_day()
    if not force_refresh:
        cached = strategy_plan_daily.load(symbol, as_of_date=as_of_date)
        if cached is not None:
            return cached.payload.model_copy(
                update={
                    "freshness_mode": cached.freshness_mode,
                    "source_mode": cached.source_mode,
                }
            )

    computed = planner.get_strategy_plan(symbol)
    saved = strategy_plan_daily.save(symbol, computed)
    return saved.payload.model_copy(
        update={
            "freshness_mode": saved.freshness_mode,
            "source_mode": saved.source_mode,
        }
    )
