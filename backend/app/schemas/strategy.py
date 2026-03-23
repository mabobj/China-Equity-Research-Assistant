"""结构化交易策略输出 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PriceRange(BaseModel):
    """价格区间。"""

    model_config = ConfigDict(extra="forbid")

    low: float
    high: float


class StrategyPlan(BaseModel):
    """结构化交易策略计划。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    as_of_date: date
    action: Literal["BUY", "WATCH", "AVOID"]
    strategy_type: Literal["pullback", "breakout", "wait", "no_trade"]
    entry_window: str
    ideal_entry_range: Optional[PriceRange] = None
    entry_triggers: list[str]
    avoid_if: list[str]
    initial_position_hint: Optional[Literal["small", "medium"]] = None
    stop_loss_price: Optional[float] = None
    stop_loss_rule: str
    take_profit_range: Optional[PriceRange] = None
    take_profit_rule: str
    hold_rule: str
    sell_rule: str
    review_timeframe: str
    confidence: int = Field(ge=0, le=100)
