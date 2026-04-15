"""Schemas for the initial screener factor system."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lineage import LineageMetadata


LegacyScreenerListType = Literal["BUY_CANDIDATE", "WATCHLIST", "AVOID"]
ScreenerListType = Literal[
    "READY_TO_BUY",
    "WATCH_PULLBACK",
    "WATCH_BREAKOUT",
    "RESEARCH_ONLY",
    "AVOID",
]
ScreenerActionNow = Literal[
    "BUY_NOW",
    "WAIT_PULLBACK",
    "WAIT_BREAKOUT",
    "RESEARCH_ONLY",
    "AVOID",
]
QualityStatus = Literal["ok", "warning", "degraded", "failed"]
AtrPctState = Literal["low", "normal", "high", "unknown"]
RangeState = Literal["compressed", "normal", "expanded", "unknown"]
DistanceState = Literal["near", "mid", "far", "unknown"]
LiquidityState = Literal["low", "normal", "high", "unknown"]
LiquidityRatioState = Literal["contracting", "normal", "expanding", "unknown"]


class ScreenerRawInputs(BaseModel):
    """Minimal normalized raw inputs used by the screener factor pipeline."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: Optional[str] = None
    market: Optional[str] = None
    board: Optional[str] = None
    industry: Optional[str] = None
    list_date: Optional[date] = None
    latest_trade_date: Optional[date] = None
    list_status: Optional[str] = None
    is_st: Optional[bool] = None
    is_suspended: Optional[bool] = None
    bars_count: Optional[int] = Field(default=None, ge=0)
    latest_close: Optional[float] = None
    latest_volume: Optional[float] = None
    latest_amount: Optional[float] = None


class ScreenerProcessMetrics(BaseModel):
    """Deterministic intermediate metrics computed from raw daily bars."""

    model_config = ConfigDict(extra="forbid")

    ma_5: Optional[float] = None
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_60: Optional[float] = None
    ma_120: Optional[float] = None
    ma_20_slope: Optional[float] = None
    ma_60_slope: Optional[float] = None
    close_percentile_60d: Optional[float] = None
    return_20d: Optional[float] = None
    return_60d: Optional[float] = None
    atr_20: Optional[float] = None
    atr_20_pct: Optional[float] = None
    range_20d: Optional[float] = None
    volatility_20d: Optional[float] = None
    avg_amount_5d: Optional[float] = None
    avg_amount_20d: Optional[float] = None
    amount_ratio_5d_20d: Optional[float] = None
    support_level_20d: Optional[float] = None
    resistance_level_20d: Optional[float] = None
    distance_to_support_pct: Optional[float] = None
    distance_to_resistance_pct: Optional[float] = None


class ScreenerAtomicFactors(BaseModel):
    """Atomic screener factors derived from process metrics."""

    model_config = ConfigDict(extra="forbid")

    basic_universe_eligibility: Optional[bool] = None
    close_above_ma20: Optional[bool] = None
    close_above_ma60: Optional[bool] = None
    ma20_above_ma60: Optional[bool] = None
    ma20_slope_positive: Optional[bool] = None
    ma60_slope_positive: Optional[bool] = None
    trend_state_basic: Optional[Literal["up", "neutral", "down"]] = None
    return_20d_strength: Optional[float] = None
    return_60d_strength: Optional[float] = None
    close_percentile_strength: Optional[float] = None
    atr_pct_state: Optional[AtrPctState] = None
    range_state: Optional[RangeState] = None
    near_support: Optional[bool] = None
    breakout_ready: Optional[bool] = None
    distance_to_resistance_state: Optional[DistanceState] = None
    amount_level_state: Optional[LiquidityState] = None
    amount_ratio_state: Optional[LiquidityRatioState] = None
    liquidity_pass: Optional[bool] = None
    is_new_listing_risk: Optional[bool] = None
    is_st_risk: Optional[bool] = None
    is_suspended_risk: Optional[bool] = None


class ScreenerCrossSectionFactors(BaseModel):
    """Cross-sectional and persistence factors for one screener batch."""

    model_config = ConfigDict(extra="forbid")

    universe_size: Optional[int] = Field(default=None, ge=0)
    industry_bucket: Optional[str] = None
    amount_rank_pct: Optional[float] = None
    return_20d_rank_pct: Optional[float] = None
    trend_score_raw: Optional[float] = None
    trend_score_rank_pct: Optional[float] = None
    atr_pct_rank_pct: Optional[float] = None
    industry_relative_strength_rank_pct: Optional[float] = None
    trend_persistence_5d: Optional[float] = None
    liquidity_persistence_5d: Optional[float] = None
    breakout_readiness_persistence_5d: Optional[float] = None
    volatility_regime_stability: Optional[float] = None


class ScreenerCompositeScore(BaseModel):
    """Composite score output before final bucket selection."""

    model_config = ConfigDict(extra="forbid")

    screener_score: int = Field(ge=0, le=100)
    alpha_score: Optional[int] = Field(default=None, ge=0, le=100)
    trigger_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_score: Optional[int] = Field(default=None, ge=0, le=100)
    list_type: LegacyScreenerListType
    v2_list_type: ScreenerListType
    action_now: Optional[ScreenerActionNow] = None
    quality_penalty_applied: bool = False
    quality_penalty_weight: Optional[float] = None


class ScreenerSelectionDecision(BaseModel):
    """Machine-readable selection decision for one stock."""

    model_config = ConfigDict(extra="forbid")

    list_type: LegacyScreenerListType
    v2_list_type: ScreenerListType
    action_now: Optional[ScreenerActionNow] = None
    selection_reasons: list[str] = Field(default_factory=list)
    exclusion_reasons: list[str] = Field(default_factory=list)
    top_positive_factors: list[str] = Field(default_factory=list)
    top_negative_factors: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    short_reason: Optional[str] = None
    quality_flags: list[str] = Field(default_factory=list)


class ScreenerFactorSnapshot(BaseModel):
    """Full initial screener factor snapshot for one symbol and one day."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    dataset: str = "screener_factor_snapshot_daily"
    dataset_version: str
    schema_version: int = Field(default=1, ge=1)
    generated_at: Optional[datetime] = None
    provider_used: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    raw_inputs: Optional[ScreenerRawInputs] = None
    process_metrics: ScreenerProcessMetrics = Field(default_factory=ScreenerProcessMetrics)
    atomic_factors: ScreenerAtomicFactors = Field(default_factory=ScreenerAtomicFactors)
    cross_section_factors: ScreenerCrossSectionFactors = Field(
        default_factory=ScreenerCrossSectionFactors,
    )
    composite_score: Optional[ScreenerCompositeScore] = None
    selection_decision: Optional[ScreenerSelectionDecision] = None
    lineage_metadata: Optional[LineageMetadata] = None
    warning_messages: list[str] = Field(default_factory=list)


def build_screener_dataset_version(
    *,
    dataset: str,
    as_of_date: date,
    symbol: Optional[str] = None,
    revision: int = 1,
) -> str:
    """Build a deterministic dataset version for daily screener products."""

    symbol_key = symbol or "global"
    normalized_dataset = dataset.strip() or "screener_factor_snapshot_daily"
    normalized_revision = max(revision, 1)
    return f"{normalized_dataset}:{as_of_date.isoformat()}:{symbol_key}:v{normalized_revision}"
