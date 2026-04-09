"""Structured strategy routes."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_strategy_plan_daily_dataset, get_strategy_planner
from app.schemas.strategy import StrategyPlan
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/{symbol}", response_model=StrategyPlan)
def get_strategy_plan(
    symbol: str,
    force_refresh: bool = Query(default=False),
    as_of_date: date | None = Query(default=None),
    planner: Any = Depends(get_strategy_planner),
    strategy_plan_daily: Any = Depends(get_strategy_plan_daily_dataset),
) -> StrategyPlan:
    """Return the structured strategy plan."""

    resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
    if not force_refresh:
        cached = strategy_plan_daily.load(symbol, as_of_date=resolved_as_of_date)
        if cached is not None:
            return cached.payload.model_copy(
                update={
                    "freshness_mode": cached.freshness_mode,
                    "source_mode": cached.source_mode,
                }
            )
    if as_of_date is not None:
        raise HTTPException(
            status_code=400,
            detail="指定 as_of_date 时，当前 strategy 仅支持读取已有日级快照，暂不支持历史重算。",
        )

    computed = planner.get_strategy_plan(symbol)
    saved = strategy_plan_daily.save(symbol, computed)
    return saved.payload.model_copy(
        update={
            "freshness_mode": saved.freshness_mode,
            "source_mode": saved.source_mode,
        }
    )
