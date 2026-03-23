"""结构化交易策略路由。"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_strategy_planner
from app.schemas.strategy import StrategyPlan

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/{symbol}", response_model=StrategyPlan)
def get_strategy_plan(
    symbol: str,
    planner: Any = Depends(get_strategy_planner),
) -> StrategyPlan:
    """返回结构化交易策略计划。"""
    return planner.get_strategy_plan(symbol)
