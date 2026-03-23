"""结构化选股结果 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScreenerCandidate(BaseModel):
    """单个选股候选结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    list_type: Literal["BUY_CANDIDATE", "WATCHLIST", "AVOID"]
    rank: int = Field(ge=1)
    screener_score: int = Field(ge=0, le=100)
    trend_state: Literal["up", "neutral", "down"]
    trend_score: int = Field(ge=0, le=100)
    latest_close: float
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    short_reason: str


class ScreenerRunResponse(BaseModel):
    """一次选股运行的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    total_symbols: int = Field(ge=0)
    scanned_symbols: int = Field(ge=0)
    buy_candidates: list[ScreenerCandidate]
    watch_candidates: list[ScreenerCandidate]
    avoid_candidates: list[ScreenerCandidate]
