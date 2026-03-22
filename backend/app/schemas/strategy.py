"""Schemas for strategy outputs."""

from pydantic import BaseModel, ConfigDict


class StrategyPlan(BaseModel):
    """Structured trading strategy schema."""

    model_config = ConfigDict(extra="forbid")

    action: str
    entry_type: str
    ideal_entry_range: list[float]
    add_position_rules: list[str]
    stop_loss_rule: str
    take_profit_rule: str
    hold_rule: str
    sell_rule: str
    review_timeframe: str
