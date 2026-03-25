"""Build lightweight factor and trigger scores from technical snapshots."""

from __future__ import annotations

from app.schemas.factor import AlphaScore, FactorScoreBreakdown, TriggerScore
from app.schemas.technical import TechnicalSnapshot
from app.services.factor_service.preprocess import clamp_score


def build_alpha_score(snapshot: TechnicalSnapshot) -> AlphaScore:
    """Build a placeholder alpha score while keeping current screener behavior stable."""
    score = float(snapshot.trend_score)
    breakdown: list[FactorScoreBreakdown] = [
        FactorScoreBreakdown(
            factor_name="trend_core",
            raw_value=float(snapshot.trend_score),
            score=float(snapshot.trend_score),
            weight=1.0,
            note="直接复用当前 trend_score 作为过渡版 alpha 核心。",
        )
    ]

    trend_adjustment = 0.0
    if snapshot.trend_state == "up":
        trend_adjustment = 10.0
    elif snapshot.trend_state == "down":
        trend_adjustment = -18.0
    score += trend_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="trend_state_adjustment",
            raw_value=trend_adjustment,
            score=clamp_score(50 + trend_adjustment),
            weight=0.0,
            note="趋势状态对 alpha 的加减分。",
        )
    )

    volatility_adjustment = 0.0
    if snapshot.volatility_state == "low":
        volatility_adjustment = 4.0
    elif snapshot.volatility_state == "high":
        volatility_adjustment = -10.0
    score += volatility_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="volatility_adjustment",
            raw_value=volatility_adjustment,
            score=clamp_score(50 + volatility_adjustment),
            weight=0.0,
            note="低波动加分，高波动减分。",
        )
    )

    ma20 = snapshot.moving_averages.ma20
    ma20_adjustment = 0.0
    if ma20 is not None:
        ma20_adjustment = 6.0 if snapshot.latest_close >= ma20 else -8.0
        score += ma20_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="price_vs_ma20",
            raw_value=ma20,
            score=clamp_score(50 + ma20_adjustment),
            weight=0.0,
            note="价格相对 MA20 的位置。",
        )
    )

    volume_ratio = snapshot.volume_metrics.volume_ratio_to_ma20
    volume_adjustment = 0.0
    if volume_ratio is not None:
        if volume_ratio >= 1.1:
            volume_adjustment = 6.0
        elif volume_ratio < 0.8:
            volume_adjustment = -5.0
        score += volume_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="volume_ratio_to_ma20",
            raw_value=volume_ratio,
            score=clamp_score(50 + volume_adjustment),
            weight=0.0,
            note="量能对 alpha 的辅助加减分。",
        )
    )

    support_adjustment = 0.0
    if snapshot.support_level is not None and snapshot.support_level > 0:
        support_distance = (
            snapshot.latest_close - snapshot.support_level
        ) / snapshot.support_level
        if snapshot.latest_close < snapshot.support_level:
            support_adjustment = -12.0
        elif support_distance <= 0.05:
            support_adjustment = 4.0
        score += support_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="support_distance",
            raw_value=snapshot.support_level,
            score=clamp_score(50 + support_adjustment),
            weight=0.0,
            note="支撑位附近加分，跌破支撑减分。",
        )
    )

    resistance_adjustment = 0.0
    if snapshot.resistance_level is not None and snapshot.latest_close > 0:
        resistance_distance = (
            snapshot.resistance_level - snapshot.latest_close
        ) / snapshot.latest_close
        if 0 <= resistance_distance <= 0.03 and snapshot.trend_state == "up":
            resistance_adjustment = 5.0
            score += resistance_adjustment
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="resistance_distance",
            raw_value=snapshot.resistance_level,
            score=clamp_score(50 + resistance_adjustment),
            weight=0.0,
            note="接近突破位时给予加分。",
        )
    )

    return AlphaScore(
        total_score=clamp_score(score),
        breakdown=breakdown,
    )


def build_trigger_score(snapshot: TechnicalSnapshot) -> TriggerScore:
    """Build a lightweight trigger score reserved for future trigger engine."""
    score = 50.0
    breakdown: list[FactorScoreBreakdown] = []

    if snapshot.trend_state == "up":
        score += 15.0
    elif snapshot.trend_state == "down":
        score -= 20.0
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="trend_trigger",
            raw_value=float(snapshot.trend_score),
            score=clamp_score(score),
            weight=1.0,
            note="趋势方向对触发优先级的影响。",
        )
    )

    if snapshot.support_level is not None and snapshot.support_level > 0:
        support_distance = (
            snapshot.latest_close - snapshot.support_level
        ) / snapshot.support_level
        if support_distance <= 0.05:
            score += 10.0
    if snapshot.resistance_level is not None and snapshot.latest_close > 0:
        resistance_distance = (
            snapshot.resistance_level - snapshot.latest_close
        ) / snapshot.latest_close
        if 0 <= resistance_distance <= 0.03:
            score += 8.0

    volume_ratio = snapshot.volume_metrics.volume_ratio_to_ma20
    if volume_ratio is not None and volume_ratio >= 1.1:
        score += 6.0
    elif volume_ratio is not None and volume_ratio < 0.8:
        score -= 8.0

    total_score = clamp_score(score)
    if total_score >= 70 and snapshot.trend_state == "up":
        trigger_state = "ready"
    elif total_score >= 45 and snapshot.trend_state != "down":
        trigger_state = "watch"
    else:
        trigger_state = "avoid"

    return TriggerScore(
        total_score=total_score,
        trigger_state=trigger_state,
        breakdown=breakdown,
    )

