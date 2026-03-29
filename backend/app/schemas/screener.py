"""结构化选股结果 schema。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRef
from app.schemas.strategy import PriceRange


LegacyScreenerListType = Literal["BUY_CANDIDATE", "WATCHLIST", "AVOID"]
ScreenerListType = Literal[
    "READY_TO_BUY",
    "WATCH_PULLBACK",
    "WATCH_BREAKOUT",
    "RESEARCH_ONLY",
    "AVOID",
]


class ScreenerCandidate(BaseModel):
    """单个选股候选结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    list_type: LegacyScreenerListType
    v2_list_type: ScreenerListType = "RESEARCH_ONLY"
    rank: int = Field(ge=1)
    screener_score: int = Field(ge=0, le=100)
    alpha_score: int = Field(default=50, ge=0, le=100)
    trigger_score: int = Field(default=50, ge=0, le=100)
    risk_score: int = Field(default=50, ge=0, le=100)
    trend_state: Literal["up", "neutral", "down"]
    trend_score: int = Field(ge=0, le=100)
    latest_close: float
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    top_positive_factors: list[str] = Field(default_factory=list)
    top_negative_factors: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    short_reason: str
    headline_verdict: Optional[str] = None
    action_now: Optional[Literal[
        "BUY_NOW",
        "WAIT_PULLBACK",
        "WAIT_BREAKOUT",
        "RESEARCH_ONLY",
        "AVOID",
    ]] = None
    evidence_hints: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ScreenerRunResponse(BaseModel):
    """一次初筛运行的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None
    total_symbols: int = Field(ge=0)
    scanned_symbols: int = Field(ge=0)
    buy_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    watch_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    avoid_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    ready_to_buy_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    watch_pullback_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    watch_breakout_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    research_only_candidates: list[ScreenerCandidate] = Field(default_factory=list)


class DeepScreenerCandidate(BaseModel):
    """深筛后的单个候选结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    base_list_type: LegacyScreenerListType
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
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None
    total_symbols: int = Field(ge=0)
    scanned_symbols: int = Field(ge=0)
    selected_for_deep_review: int = Field(ge=0)
    deep_candidates: list[DeepScreenerCandidate]
