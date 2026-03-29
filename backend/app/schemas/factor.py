"""因子快照与分数组合 schema。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class FactorScoreBreakdown(BaseModel):
    """单个因子分项。"""

    model_config = ConfigDict(extra="forbid")

    factor_name: str
    raw_value: Optional[float] = None
    score: Optional[float] = Field(default=None, ge=0, le=100)
    weight: float = Field(ge=0, default=1.0)
    contribution: Optional[float] = None
    note: Optional[str] = None


class FactorGroupScore(BaseModel):
    """因子组分数与组内信号摘要。"""

    model_config = ConfigDict(extra="forbid")

    group_name: str
    score: Optional[float] = Field(default=None, ge=0, le=100)
    top_positive_signals: list[str] = Field(default_factory=list)
    top_negative_signals: list[str] = Field(default_factory=list)


class AlphaScore(BaseModel):
    """横截面 alpha 分数。"""

    model_config = ConfigDict(extra="forbid")

    total_score: int = Field(ge=0, le=100)
    breakdown: list[FactorScoreBreakdown] = Field(default_factory=list)


class TriggerScore(BaseModel):
    """触发分数。"""

    model_config = ConfigDict(extra="forbid")

    total_score: int = Field(ge=0, le=100)
    trigger_state: Literal["pullback", "breakout", "neutral", "avoid"]
    breakdown: list[FactorScoreBreakdown] = Field(default_factory=list)


class RiskScore(BaseModel):
    """风险分数，数值越高表示风险越高。"""

    model_config = ConfigDict(extra="forbid")

    total_score: int = Field(ge=0, le=100)
    breakdown: list[FactorScoreBreakdown] = Field(default_factory=list)


class FactorSnapshot(BaseModel):
    """结构化因子快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None
    raw_factors: dict[str, Optional[float]] = Field(default_factory=dict)
    normalized_factors: dict[str, Optional[float]] = Field(default_factory=dict)
    factor_group_scores: list[FactorGroupScore] = Field(default_factory=list)
    alpha_score: AlphaScore
    trigger_score: TriggerScore
    risk_score: RiskScore
