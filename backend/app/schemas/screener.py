"""结构化选股结果 schema。"""

from __future__ import annotations

from datetime import date, datetime
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
    calculated_at: Optional[datetime] = None
    rule_version: Optional[str] = None
    rule_summary: Optional[str] = None
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


class ScreenerBatchRecord(BaseModel):
    """初筛批次台账记录。"""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    trade_date: date
    run_id: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    finished_at: Optional[datetime] = None
    universe_size: int = Field(default=0, ge=0)
    scanned_size: int = Field(default=0, ge=0)
    rule_version: str
    batch_size: Optional[int] = Field(default=None, ge=1)
    max_symbols: Optional[int] = Field(default=None, ge=1)
    top_n: Optional[int] = Field(default=None, ge=1)
    workflow_name: str = "screener_run"
    warning_messages: list[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None


class ScreenerSymbolResult(BaseModel):
    """批次下单只股票的筛选结果。"""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    symbol: str
    name: str
    list_type: ScreenerListType
    screener_score: int = Field(ge=0, le=100)
    trend_state: Literal["up", "neutral", "down"]
    trend_score: int = Field(ge=0, le=100)
    latest_close: float
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    short_reason: str
    calculated_at: datetime
    rule_version: str
    rule_summary: str
    action_now: Optional[Literal[
        "BUY_NOW",
        "WAIT_PULLBACK",
        "WAIT_BREAKOUT",
        "RESEARCH_ONLY",
        "AVOID",
    ]] = None
    headline_verdict: Optional[str] = None
    evidence_hints: list[str] = Field(default_factory=list)
    fail_reason: Optional[str] = None


class ScreenerLatestBatchResponse(BaseModel):
    """最新可查看批次摘要。"""

    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    batch: Optional[ScreenerBatchRecord] = None
    results: list[ScreenerSymbolResult] = Field(default_factory=list)
    total_results: int = Field(default=0, ge=0)


class ScreenerCursorResetResponse(BaseModel):
    """初筛游标重置结果。"""

    model_config = ConfigDict(extra="forbid")

    reset_at: datetime
    message: str


class ScreenerBatchDetailResponse(BaseModel):
    """批次详情。"""

    model_config = ConfigDict(extra="forbid")

    batch: ScreenerBatchRecord


class ScreenerBatchResultsResponse(BaseModel):
    """批次结果列表。"""

    model_config = ConfigDict(extra="forbid")

    batch: ScreenerBatchRecord
    results: list[ScreenerSymbolResult] = Field(default_factory=list)


class ScreenerSymbolResultResponse(BaseModel):
    """单只股票筛选结果详情。"""

    model_config = ConfigDict(extra="forbid")

    batch: ScreenerBatchRecord
    result: ScreenerSymbolResult
