"""个股研判 v2 结构化输出 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.strategy import PriceRange


class FactorProfileView(BaseModel):
    """因子画像。"""

    model_config = ConfigDict(extra="forbid")

    strongest_factor_groups: list[str] = Field(default_factory=list)
    weakest_factor_groups: list[str] = Field(default_factory=list)
    alpha_score: int = Field(ge=0, le=100)
    trigger_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    concise_summary: str


class TechnicalView(BaseModel):
    """技术画像。"""

    model_config = ConfigDict(extra="forbid")

    trend_state: Literal["up", "neutral", "down"]
    trigger_state: Literal[
        "near_support",
        "near_breakout",
        "neutral",
        "overstretched",
        "invalid",
    ]
    latest_close: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    key_levels: list[str] = Field(default_factory=list)
    tactical_read: str
    invalidation_hint: str


class FundamentalView(BaseModel):
    """基本面画像。"""

    model_config = ConfigDict(extra="forbid")

    quality_read: Optional[str] = None
    growth_read: Optional[str] = None
    leverage_read: Optional[str] = None
    data_completeness_note: str
    key_financial_flags: list[str] = Field(default_factory=list)


class EventView(BaseModel):
    """事件画像。"""

    model_config = ConfigDict(extra="forbid")

    recent_catalysts: list[str] = Field(default_factory=list)
    recent_risks: list[str] = Field(default_factory=list)
    event_temperature: Literal["hot", "warm", "neutral", "cool"]
    concise_summary: str


class SentimentView(BaseModel):
    """情绪画像。"""

    model_config = ConfigDict(extra="forbid")

    sentiment_bias: Literal["bullish", "neutral", "cautious", "bearish"]
    crowding_hint: str
    momentum_context: str
    concise_summary: str


class BullBearCase(BaseModel):
    """多头或空头观点。"""

    model_config = ConfigDict(extra="forbid")

    stance: Literal["bull", "bear"]
    summary: str
    reasons: list[str] = Field(default_factory=list, max_length=3)


class FinalJudgement(BaseModel):
    """最终裁决。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["BUY", "WATCH", "AVOID"]
    summary: str
    key_points: list[str] = Field(default_factory=list, max_length=3)


class StrategySummary(BaseModel):
    """策略摘要。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["BUY", "WATCH", "AVOID"]
    strategy_type: Literal["pullback", "breakout", "wait", "no_trade"]
    entry_window: str
    ideal_entry_range: Optional[PriceRange] = None
    stop_loss_price: Optional[float] = None
    take_profit_range: Optional[PriceRange] = None
    review_timeframe: str
    concise_summary: str


class StockReviewReport(BaseModel):
    """个股研判 v2 报告。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    as_of_date: date
    factor_profile: FactorProfileView
    technical_view: TechnicalView
    fundamental_view: FundamentalView
    event_view: EventView
    sentiment_view: SentimentView
    bull_case: BullBearCase
    bear_case: BullBearCase
    key_disagreements: list[str] = Field(default_factory=list)
    final_judgement: FinalJudgement
    strategy_summary: StrategySummary
    confidence: int = Field(ge=0, le=100)
