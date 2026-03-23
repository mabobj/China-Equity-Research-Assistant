"""结构化选股结果 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.strategy import PriceRange


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
    """一次初筛运行的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    total_symbols: int = Field(ge=0)
    scanned_symbols: int = Field(ge=0)
    buy_candidates: list[ScreenerCandidate]
    watch_candidates: list[ScreenerCandidate]
    avoid_candidates: list[ScreenerCandidate]


class DeepScreenerCandidate(BaseModel):
    """深筛后的单个候选结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    base_list_type: Literal["BUY_CANDIDATE", "WATCHLIST", "AVOID"]
    base_rank: int = Field(ge=1)
    base_screener_score: int = Field(ge=0, le=100)
    research_action: Literal["BUY", "WATCH", "AVOID"]
    research_overall_score: int = Field(ge=0, le=100)
    research_confidence: int = Field(ge=0, le=100)
    strategy_action: Literal["BUY", "WATCH", "AVOID"]
    strategy_type: Literal["pullback", "breakout", "wait", "no_trade"]
    ideal_entry_range: Optional[PriceRange] = None
    stop_loss_price: Optional[float] = None
    take_profit_range: Optional[PriceRange] = None
    review_timeframe: str
    thesis: str
    short_reason: str
    priority_score: int = Field(ge=0, le=100)


class DeepScreenerRunResponse(BaseModel):
    """一次深筛运行的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    total_symbols: int = Field(ge=0)
    scanned_symbols: int = Field(ge=0)
    selected_for_deep_review: int = Field(ge=0)
    deep_candidates: list[DeepScreenerCandidate]
