"""因子分数组合逻辑。"""

from __future__ import annotations

from app.schemas.factor import (
    AlphaScore,
    FactorGroupScore,
    FactorScoreBreakdown,
    RiskScore,
    TriggerScore,
)
from app.schemas.technical import TechnicalSnapshot
from app.services.factor_service.preprocess import clamp_score, weighted_average_scores


def build_alpha_score(group_scores: list[FactorGroupScore]) -> AlphaScore:
    """构建 alpha 分数。"""
    score_map = {item.group_name: item.score for item in group_scores}
    weights = {
        "trend": 0.30,
        "quality": 0.25,
        "growth": 0.20,
        "low_vol": 0.15,
        "event": 0.10,
    }
    score = weighted_average_scores(
        [(score_map.get(group_name), weight) for group_name, weight in weights.items()],
    )

    return AlphaScore(
        total_score=clamp_score(score),
        breakdown=_build_group_breakdown(
            group_scores=group_scores,
            weights=weights,
            reverse=False,
        ),
    )


def build_trigger_score(
    technical_snapshot: TechnicalSnapshot,
    *,
    alpha_score: int,
    risk_score: int,
) -> TriggerScore:
    """构建触发分数。"""
    score = 50.0
    breakdown: list[FactorScoreBreakdown] = []

    trend_bonus = (
        12.0
        if technical_snapshot.trend_state == "up"
        else -15.0 if technical_snapshot.trend_state == "down" else 0.0
    )
    score += trend_bonus
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="daily_trend_state",
            raw_value=float(technical_snapshot.trend_score),
            score=clamp_score(50 + trend_bonus),
            weight=0.25,
            contribution=round(trend_bonus, 2),
            note="日线趋势对触发分数的影响。",
        )
    )

    volume_ratio = technical_snapshot.volume_metrics.volume_ratio_to_ma20
    volume_bonus = 0.0
    if volume_ratio is not None:
        if volume_ratio >= 1.1:
            volume_bonus = 8.0
        elif volume_ratio < 0.8:
            volume_bonus = -8.0
    score += volume_bonus
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="volume_ratio_to_ma20",
            raw_value=volume_ratio,
            score=clamp_score(50 + volume_bonus),
            weight=0.20,
            contribution=round(volume_bonus, 2),
            note="量能配合度。",
        )
    )

    support_distance_pct = None
    support_bonus = 0.0
    if technical_snapshot.support_level is not None and technical_snapshot.support_level > 0:
        support_distance_pct = (
            (technical_snapshot.latest_close - technical_snapshot.support_level)
            / technical_snapshot.support_level
            * 100.0
        )
        if 0.0 <= support_distance_pct <= 4.0:
            support_bonus = 12.0
        elif support_distance_pct > 8.0:
            support_bonus = -4.0
    score += support_bonus
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="distance_to_support_pct",
            raw_value=support_distance_pct,
            score=clamp_score(50 + support_bonus),
            weight=0.25,
            contribution=round(support_bonus, 2),
            note="靠近支撑有助于形成回踩触发。",
        )
    )

    resistance_distance_pct = None
    breakout_bonus = 0.0
    if technical_snapshot.resistance_level is not None and technical_snapshot.latest_close > 0:
        resistance_distance_pct = (
            (technical_snapshot.resistance_level - technical_snapshot.latest_close)
            / technical_snapshot.latest_close
            * 100.0
        )
        if 0.0 <= resistance_distance_pct <= 2.5:
            breakout_bonus = 10.0
        elif resistance_distance_pct > 7.0:
            breakout_bonus = -4.0
    score += breakout_bonus
    breakdown.append(
        FactorScoreBreakdown(
            factor_name="distance_to_resistance_pct",
            raw_value=resistance_distance_pct,
            score=clamp_score(50 + breakout_bonus),
            weight=0.20,
            contribution=round(breakout_bonus, 2),
            note="靠近压力位有助于形成突破观察。",
        )
    )

    score += (alpha_score - 50.0) * 0.10
    score -= max(0.0, risk_score - 50.0) * 0.12

    total_score = clamp_score(score)
    trigger_state = "neutral"
    if technical_snapshot.trend_state == "down" or risk_score >= 75:
        trigger_state = "avoid"
    elif support_distance_pct is not None and 0.0 <= support_distance_pct <= 4.0 and total_score >= 65:
        trigger_state = "pullback"
    elif resistance_distance_pct is not None and 0.0 <= resistance_distance_pct <= 2.5 and total_score >= 65:
        trigger_state = "breakout"
    elif total_score < 45:
        trigger_state = "avoid"

    return TriggerScore(
        total_score=total_score,
        trigger_state=trigger_state,
        breakdown=breakdown,
    )


def build_risk_score(
    group_scores: list[FactorGroupScore],
    technical_snapshot: TechnicalSnapshot,
) -> RiskScore:
    """构建风险分数，越高表示风险越大。"""
    score_map = {item.group_name: item.score for item in group_scores}
    base_risk = 50.0

    low_vol_score = score_map.get("low_vol")
    quality_score = score_map.get("quality")
    growth_score = score_map.get("growth")
    event_score = score_map.get("event")

    if low_vol_score is not None:
        base_risk += (50.0 - low_vol_score) * 0.45
    if quality_score is not None:
        base_risk += (50.0 - quality_score) * 0.25
    if growth_score is not None:
        base_risk += (50.0 - growth_score) * 0.15
    if event_score is not None:
        base_risk += (50.0 - event_score) * 0.10
    if technical_snapshot.trend_state == "down":
        base_risk += 12.0
    elif technical_snapshot.trend_state == "up":
        base_risk -= 6.0
    if technical_snapshot.volatility_state == "high":
        base_risk += 12.0

    return RiskScore(
        total_score=clamp_score(base_risk),
        breakdown=_build_group_breakdown(
            group_scores=group_scores,
            weights={
                "low_vol": 0.45,
                "quality": 0.25,
                "growth": 0.15,
                "event": 0.10,
            },
            reverse=True,
        ),
    )


def _build_group_breakdown(
    *,
    group_scores: list[FactorGroupScore],
    weights: dict[str, float],
    reverse: bool,
) -> list[FactorScoreBreakdown]:
    breakdown: list[FactorScoreBreakdown] = []
    for item in group_scores:
        weight = weights.get(item.group_name, 0.0)
        normalized_score = None
        contribution = None
        if item.score is not None:
            normalized_score = (100.0 - item.score) if reverse else item.score
            contribution = round(normalized_score * weight, 2)

        breakdown.append(
            FactorScoreBreakdown(
                factor_name=item.group_name,
                raw_value=item.score,
                score=normalized_score,
                weight=weight,
                contribution=contribution,
                note="因子组 {group_name} 的组合贡献。".format(
                    group_name=item.group_name,
                ),
            )
        )
    return breakdown
