"""Schemas for trade records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TradeRecord(BaseModel):
    """Structured trade record schema."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    executed_at: datetime
    price: float
    quantity: int
    side: str
    reason: str
    strategy_snapshot: str
