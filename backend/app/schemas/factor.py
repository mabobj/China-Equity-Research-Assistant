"""Factor snapshot schemas."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class FactorScoreBreakdown(BaseModel):
    """One factor score item."""

    model_config = ConfigDict(extra="forbid")

    factor_name: str
    raw_value: Optional[float] = None
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0)
    note: Optional[str] = None


class AlphaScore(BaseModel):
    """Composite alpha score."""

    model_config = ConfigDict(extra="forbid")

    total_score: int = Field(ge=0, le=100)
    breakdown: list[FactorScoreBreakdown]


class TriggerScore(BaseModel):
    """Composite trigger score."""

    model_config = ConfigDict(extra="forbid")

    total_score: int = Field(ge=0, le=100)
    trigger_state: Literal["ready", "watch", "avoid"]
    breakdown: list[FactorScoreBreakdown]


class FactorSnapshot(BaseModel):
    """Minimal factor snapshot reserved for future multi-factor expansion."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    latest_close: float
    trend_state: Literal["up", "neutral", "down"]
    trend_score: int = Field(ge=0, le=100)
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    alpha_score: AlphaScore
    trigger_score: TriggerScore

