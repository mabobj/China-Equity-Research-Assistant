"""角色化裁决骨架相关 schema。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import StockReviewReport, StrategySummary


class DebatePoint(BaseModel):
    """结构化辩论要点。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    detail: str


class AnalystView(BaseModel):
    """单个角色分析员的结构化观点。"""

    model_config = ConfigDict(extra="forbid")

    role: Literal[
        "technical_analyst",
        "fundamental_analyst",
        "event_analyst",
        "sentiment_analyst",
    ]
    summary: str
    action_bias: Literal["supportive", "neutral", "cautious", "negative"]
    positive_points: list[DebatePoint] = Field(default_factory=list)
    caution_points: list[DebatePoint] = Field(default_factory=list)
    key_levels: list[str] = Field(default_factory=list)


class AnalystViewsBundle(BaseModel):
    """四类 analyst 观点集合。"""

    model_config = ConfigDict(extra="forbid")

    technical: AnalystView
    fundamental: AnalystView
    event: AnalystView
    sentiment: AnalystView


class BullCase(BaseModel):
    """多头研究员观点。"""

    model_config = ConfigDict(extra="forbid")

    summary: str
    reasons: list[DebatePoint] = Field(default_factory=list)


class BearCase(BaseModel):
    """空头研究员观点。"""

    model_config = ConfigDict(extra="forbid")

    summary: str
    reasons: list[DebatePoint] = Field(default_factory=list)


class ChiefJudgement(BaseModel):
    """首席分析员裁决。"""

    model_config = ConfigDict(extra="forbid")

    final_action: Literal["BUY", "WATCH", "AVOID"]
    summary: str
    decisive_points: list[str] = Field(default_factory=list)
    key_disagreements: list[str] = Field(default_factory=list)


class RiskReview(BaseModel):
    """风险复核结论。"""

    model_config = ConfigDict(extra="forbid")

    risk_level: Literal["low", "medium", "high"]
    summary: str
    execution_reminders: list[str] = Field(default_factory=list)


class DebateReviewReport(BaseModel):
    """角色化裁决骨架版单票报告。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    as_of_date: date
    analyst_views: AnalystViewsBundle
    bull_case: BullCase
    bear_case: BearCase
    key_disagreements: list[str] = Field(default_factory=list)
    chief_judgement: ChiefJudgement
    risk_review: RiskReview
    final_action: Literal["BUY", "WATCH", "AVOID"]
    strategy_summary: StrategySummary
    confidence: int = Field(ge=0, le=100)
    runtime_mode: Literal["rule_based", "llm"] = "rule_based"


class SingleStockResearchInputs(BaseModel):
    """单票角色化流程输入节点。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    review_report: StockReviewReport
    strategy_summary: StrategySummary
    factor_alpha_score: int = Field(ge=0, le=100)
    factor_risk_score: int = Field(ge=0, le=100)
    trigger_state: str


class AnalystViewsBuild(BaseModel):
    """分析员观点节点输出。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    analyst_views: AnalystViewsBundle


class BullBearDebateBuild(BaseModel):
    """多空观点节点输出。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    bull_case: BullCase
    bear_case: BearCase
    key_disagreements: list[str] = Field(default_factory=list)


class ChiefJudgementBuild(BaseModel):
    """首席裁决节点输出。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    chief_judgement: ChiefJudgement
    risk_review: RiskReview


class StrategyFinalize(BaseModel):
    """策略收束节点输出。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    final_action: Literal["BUY", "WATCH", "AVOID"]
    strategy_summary: StrategySummary
    confidence: int = Field(ge=0, le=100)
