"""盘中快照与触发快照 schema。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class IntradaySnapshot(BaseModel):
    """盘中分钟线快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    frequency: str
    latest_price: float
    latest_datetime: datetime
    session_high: float
    session_low: float
    session_open: float
    volume_sum: Optional[float] = None
    intraday_return_pct: Optional[float] = None
    range_pct: Optional[float] = None
    source: str


class TriggerSnapshot(BaseModel):
    """基于日线与盘中快照的轻量触发快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_datetime: datetime
    daily_trend_state: Literal["up", "neutral", "down"]
    daily_support_level: Optional[float] = None
    daily_resistance_level: Optional[float] = None
    latest_intraday_price: float
    distance_to_support_pct: Optional[float] = None
    distance_to_resistance_pct: Optional[float] = None
    trigger_state: Literal[
        "near_support",
        "near_breakout",
        "neutral",
        "overstretched",
        "invalid",
    ]
    trigger_note: str
