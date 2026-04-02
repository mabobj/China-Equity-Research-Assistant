"""交易与复盘闭环的结构化 Schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research import ResearchDataQualitySummary

TradeSide = Literal["BUY", "SELL", "ADD", "REDUCE", "SKIP"]
TradeReasonType = Literal[
    "signal_entry",
    "pullback_entry",
    "breakout_entry",
    "stop_loss",
    "take_profit",
    "time_exit",
    "manual_override",
    "watch_only",
    "skip_due_to_quality",
    "skip_due_to_risk",
]
StrategyAlignment = Literal["aligned", "partially_aligned", "not_aligned", "unknown"]
ReviewOutcomeLabel = Literal["success", "partial_success", "failure", "invalidated", "no_trade"]
DidFollowPlan = Literal["yes", "partial", "no"]

ENTRY_REASON_TYPES = {"signal_entry", "pullback_entry", "breakout_entry"}
EXIT_REASON_TYPES = {"stop_loss", "take_profit", "time_exit"}
SKIP_REASON_TYPES = {"watch_only", "skip_due_to_quality", "skip_due_to_risk"}


def validate_trade_reason_type_for_side(reason_type: TradeReasonType, side: TradeSide) -> None:
    """校验交易动作与原因类型是否匹配。"""
    if reason_type in ENTRY_REASON_TYPES and side not in {"BUY", "ADD"}:
        raise ValueError("入场类 reason_type 仅适用于 BUY/ADD。")
    if reason_type in EXIT_REASON_TYPES and side not in {"SELL", "REDUCE"}:
        raise ValueError("止盈止损类 reason_type 仅适用于 SELL/REDUCE。")
    if reason_type in SKIP_REASON_TYPES and side != "SKIP":
        raise ValueError("watch_only/skip_due_to_* 仅适用于 SKIP。")


class DecisionSourceRef(BaseModel):
    """决策快照的数据来源引用。"""

    model_config = ConfigDict(extra="forbid")

    module_name: str
    as_of_date: Optional[date] = None
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None
    note: Optional[str] = None


class DecisionSnapshotCreatePayload(BaseModel):
    """手工提交决策快照时的精简载荷。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    action: str
    confidence: int = Field(ge=0, le=100)
    technical_score: int = Field(ge=0, le=100)
    fundamental_score: int = Field(ge=0, le=100)
    event_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    thesis: str
    risks: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    invalidations: list[str] = Field(default_factory=list)
    data_quality_summary: Optional[ResearchDataQualitySummary] = None
    confidence_reasons: list[str] = Field(default_factory=list)
    runtime_mode_requested: Optional[str] = None
    runtime_mode_effective: Optional[str] = None
    predictive_score: Optional[int] = Field(default=None, ge=0, le=100)
    predictive_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predictive_model_version: Optional[str] = None
    predictive_feature_version: Optional[str] = None
    predictive_label_version: Optional[str] = None
    source_refs: list[DecisionSourceRef] = Field(default_factory=list)


class CreateDecisionSnapshotRequest(BaseModel):
    """创建决策快照请求。"""

    model_config = ConfigDict(extra="forbid")

    symbol: Optional[str] = None
    use_llm: Optional[bool] = None
    payload: Optional[DecisionSnapshotCreatePayload] = None

    @model_validator(mode="after")
    def validate_input(self) -> "CreateDecisionSnapshotRequest":
        if not self.symbol and self.payload is None:
            raise ValueError("`symbol` 与 `payload` 至少提供一项。")
        return self


class DecisionSnapshotRecord(BaseModel):
    """决策快照记录。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    symbol: str
    as_of_date: date
    action: str
    confidence: int = Field(ge=0, le=100)
    technical_score: int = Field(ge=0, le=100)
    fundamental_score: int = Field(ge=0, le=100)
    event_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    thesis: str
    risks: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    invalidations: list[str] = Field(default_factory=list)
    data_quality_summary: Optional[ResearchDataQualitySummary] = None
    confidence_reasons: list[str] = Field(default_factory=list)
    runtime_mode_requested: Optional[str] = None
    runtime_mode_effective: Optional[str] = None
    predictive_score: Optional[int] = Field(default=None, ge=0, le=100)
    predictive_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predictive_model_version: Optional[str] = None
    predictive_feature_version: Optional[str] = None
    predictive_label_version: Optional[str] = None
    source_refs: list[DecisionSourceRef] = Field(default_factory=list)
    created_at: datetime


class DecisionSnapshotListResponse(BaseModel):
    """决策快照列表响应。"""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    items: list[DecisionSnapshotRecord]


class TradeRecordBase(BaseModel):
    """交易记录通用字段。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: TradeSide
    trade_date: datetime
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = Field(default=None, gt=0)
    reason_type: TradeReasonType
    note: Optional[str] = None
    decision_snapshot_id: Optional[str] = None
    strategy_alignment: StrategyAlignment = "unknown"
    alignment_override_reason: Optional[str] = None


class CreateTradeRequest(TradeRecordBase):
    """创建交易记录请求。"""

    auto_create_snapshot: bool = False
    use_llm: Optional[bool] = None

    @model_validator(mode="after")
    def validate_trade_fields(self) -> "CreateTradeRequest":
        if self.side != "SKIP" and (self.price is None or self.quantity is None):
            raise ValueError("非 SKIP 记录必须提供 `price` 和 `quantity`。")
        validate_trade_reason_type_for_side(self.reason_type, self.side)
        return self


class UpdateTradeRequest(BaseModel):
    """更新交易记录请求。"""

    model_config = ConfigDict(extra="forbid")

    side: Optional[TradeSide] = None
    trade_date: Optional[datetime] = None
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = Field(default=None, gt=0)
    reason_type: Optional[TradeReasonType] = None
    note: Optional[str] = None
    decision_snapshot_id: Optional[str] = None
    strategy_alignment: Optional[StrategyAlignment] = None
    alignment_override_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_pair_when_both_present(self) -> "UpdateTradeRequest":
        if self.side is not None and self.reason_type is not None:
            validate_trade_reason_type_for_side(self.reason_type, self.side)
        return self


class CreateTradeFromCurrentDecisionRequest(BaseModel):
    """从当前研究上下文创建交易请求。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    use_llm: Optional[bool] = None
    side: TradeSide
    trade_date: Optional[datetime] = None
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = Field(default=None, gt=0)
    reason_type: TradeReasonType
    note: Optional[str] = None
    strategy_alignment: StrategyAlignment = "unknown"
    alignment_override_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_trade_fields(self) -> "CreateTradeFromCurrentDecisionRequest":
        if self.side != "SKIP" and (self.price is None or self.quantity is None):
            raise ValueError("非 SKIP 记录必须提供 `price` 和 `quantity`。")
        validate_trade_reason_type_for_side(self.reason_type, self.side)
        return self


class TradeRecord(TradeRecordBase):
    """交易记录。"""

    trade_id: str
    created_at: datetime
    updated_at: datetime
    decision_snapshot: Optional[DecisionSnapshotRecord] = None


class TradeListResponse(BaseModel):
    """交易列表响应。"""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    items: list[TradeRecord]


class CreateReviewRequest(BaseModel):
    """创建复盘记录请求。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    review_date: date
    linked_trade_id: Optional[str] = None
    linked_decision_snapshot_id: Optional[str] = None
    outcome_label: ReviewOutcomeLabel
    holding_days: Optional[int] = Field(default=None, ge=0)
    max_favorable_excursion: Optional[float] = None
    max_adverse_excursion: Optional[float] = None
    exit_reason: Optional[str] = None
    did_follow_plan: DidFollowPlan = "partial"
    review_summary: str
    lesson_tags: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)


class CreateReviewFromTradeRequest(BaseModel):
    """从交易记录生成复盘草稿请求。"""

    model_config = ConfigDict(extra="forbid")

    review_date: Optional[date] = None
    outcome_label: Optional[ReviewOutcomeLabel] = None
    did_follow_plan: Optional[DidFollowPlan] = None
    exit_reason: Optional[str] = None


class UpdateReviewRequest(BaseModel):
    """更新复盘记录请求。"""

    model_config = ConfigDict(extra="forbid")

    outcome_label: Optional[ReviewOutcomeLabel] = None
    holding_days: Optional[int] = Field(default=None, ge=0)
    max_favorable_excursion: Optional[float] = None
    max_adverse_excursion: Optional[float] = None
    exit_reason: Optional[str] = None
    did_follow_plan: Optional[DidFollowPlan] = None
    review_summary: Optional[str] = None
    lesson_tags: Optional[list[str]] = None
    warning_messages: Optional[list[str]] = None


class ReviewRecord(BaseModel):
    """复盘记录。"""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    symbol: str
    review_date: date
    linked_trade_id: Optional[str] = None
    linked_decision_snapshot_id: Optional[str] = None
    outcome_label: ReviewOutcomeLabel
    holding_days: Optional[int] = Field(default=None, ge=0)
    max_favorable_excursion: Optional[float] = None
    max_adverse_excursion: Optional[float] = None
    exit_reason: Optional[str] = None
    did_follow_plan: DidFollowPlan
    review_summary: str
    lesson_tags: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    linked_trade: Optional[TradeRecord] = None
    linked_decision_snapshot: Optional[DecisionSnapshotRecord] = None


class ReviewListResponse(BaseModel):
    """复盘列表响应。"""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    items: list[ReviewRecord]


class PositionCase(BaseModel):
    """轻量交易案例聚合对象。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    symbol: str
    trade_ids: list[str] = Field(default_factory=list)
    review_ids: list[str] = Field(default_factory=list)
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    net_quantity: float = 0.0
    notes: dict[str, Any] = Field(default_factory=dict)
