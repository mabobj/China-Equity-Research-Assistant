"""选股评分与兼容分桶规则。"""

from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.factor import FactorSnapshot
from app.schemas.screener_factors import (
    ScreenerCompositeScore,
    ScreenerFactorSnapshot,
    ScreenerSelectionDecision,
)
from app.schemas.technical import TechnicalSnapshot
from app.services.factor_service.reason_builder import build_reason_summary


@dataclass(frozen=True)
class ScreenerScoreResult:
    """选股评分结果。"""

    screener_score: int
    alpha_score: int
    trigger_score: int
    risk_score: int
    list_type: str
    v2_list_type: str
    top_positive_factors: list[str]
    top_negative_factors: list[str]
    risk_notes: list[str]
    short_reason: str


def score_technical_snapshot(snapshot: TechnicalSnapshot) -> ScreenerScoreResult:
    """兼容旧逻辑的兜底评分。"""
    return score_technical_snapshot_with_scheme(snapshot)


def score_technical_snapshot_with_scheme(
    snapshot: TechnicalSnapshot,
    *,
    factor_weight_config: dict[str, Any] | None = None,
    threshold_config: dict[str, Any] | None = None,
) -> ScreenerScoreResult:
    """兼容旧逻辑的兜底评分，并允许有限方案覆盖。"""
    score = float(snapshot.trend_score)

    if snapshot.trend_state == "up":
        score += 10.0
    elif snapshot.trend_state == "down":
        score -= 18.0

    if snapshot.volatility_state == "low":
        score += 4.0
    elif snapshot.volatility_state == "high":
        score -= 10.0

    ma20 = snapshot.moving_averages.ma20
    if ma20 is not None:
        score += 6.0 if snapshot.latest_close >= ma20 else -8.0

    volume_ratio = snapshot.volume_metrics.volume_ratio_to_ma20
    if volume_ratio is not None:
        if volume_ratio >= 1.1:
            score += 6.0
        elif volume_ratio < 0.8:
            score -= 5.0

    alpha_score = _clamp_score(score)
    trigger_score = alpha_score
    risk_score = _estimate_legacy_risk_score(snapshot)
    trigger_state = _infer_legacy_trigger_state(snapshot)
    screener_score = _build_screener_score(
        alpha_score,
        trigger_score,
        risk_score,
        factor_weight_config=factor_weight_config,
    )
    v2_list_type = _classify_v2_list_type(
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        screener_score=screener_score,
        technical_snapshot=snapshot,
        trigger_state=trigger_state,
        threshold_config=threshold_config,
    )

    return ScreenerScoreResult(
        screener_score=screener_score,
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        list_type=_to_legacy_list_type(v2_list_type),
        v2_list_type=v2_list_type,
        top_positive_factors=[],
        top_negative_factors=[],
        risk_notes=[],
        short_reason=_build_legacy_short_reason(snapshot, v2_list_type),
    )


def score_factor_snapshot(
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
) -> ScreenerScoreResult:
    """基于因子快照评分。"""
    return score_factor_snapshot_with_scheme(
        factor_snapshot,
        technical_snapshot,
    )


def score_factor_snapshot_with_scheme(
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
    *,
    factor_weight_config: dict[str, Any] | None = None,
    threshold_config: dict[str, Any] | None = None,
) -> ScreenerScoreResult:
    """基于因子快照评分，并允许有限方案覆盖。"""
    alpha_score = factor_snapshot.alpha_score.total_score
    trigger_score = factor_snapshot.trigger_score.total_score
    risk_score = factor_snapshot.risk_score.total_score
    screener_score = _build_screener_score(
        alpha_score,
        trigger_score,
        risk_score,
        factor_weight_config=factor_weight_config,
    )
    v2_list_type = _classify_v2_list_type(
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        screener_score=screener_score,
        technical_snapshot=technical_snapshot,
        trigger_state=factor_snapshot.trigger_score.trigger_state,
        threshold_config=threshold_config,
    )
    reasons = build_reason_summary(factor_snapshot)

    return ScreenerScoreResult(
        screener_score=screener_score,
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        list_type=_to_legacy_list_type(v2_list_type),
        v2_list_type=v2_list_type,
        top_positive_factors=reasons.top_positive_factors,
        top_negative_factors=reasons.top_negative_factors,
        risk_notes=reasons.risk_notes,
        short_reason=reasons.short_reason,
    )


def score_screener_factor_snapshot(
    screener_factor_snapshot: ScreenerFactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
) -> ScreenerScoreResult:
    """Score the new initial screener factor snapshot."""
    return score_screener_factor_snapshot_with_scheme(
        screener_factor_snapshot,
        technical_snapshot,
    )


def score_screener_factor_snapshot_with_scheme(
    screener_factor_snapshot: ScreenerFactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
    *,
    factor_weight_config: dict[str, Any] | None = None,
    threshold_config: dict[str, Any] | None = None,
) -> ScreenerScoreResult:
    """Score the new initial screener factor snapshot with optional scheme overrides."""

    alpha_score = _score_screener_alpha(screener_factor_snapshot)
    trigger_state = _infer_screener_trigger_state(screener_factor_snapshot)
    trigger_score = _score_screener_trigger(
        screener_factor_snapshot=screener_factor_snapshot,
        trigger_state=trigger_state,
    )
    risk_score = _score_screener_risk(screener_factor_snapshot, technical_snapshot)
    screener_score = _build_screener_score(
        alpha_score,
        trigger_score,
        risk_score,
        factor_weight_config=factor_weight_config,
    )
    v2_list_type = _classify_v2_list_type(
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        screener_score=screener_score,
        technical_snapshot=technical_snapshot,
        trigger_state=trigger_state,
        threshold_config=threshold_config,
    )
    reasons = _build_screener_reason_summary(
        screener_factor_snapshot=screener_factor_snapshot,
        v2_list_type=v2_list_type,
        trigger_state=trigger_state,
    )

    return ScreenerScoreResult(
        screener_score=screener_score,
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        list_type=_to_legacy_list_type(v2_list_type),
        v2_list_type=v2_list_type,
        top_positive_factors=reasons.top_positive_factors,
        top_negative_factors=reasons.top_negative_factors,
        risk_notes=reasons.risk_notes,
        short_reason=reasons.short_reason,
    )


def apply_score_to_screener_factor_snapshot(
    *,
    screener_factor_snapshot: ScreenerFactorSnapshot,
    score_result: ScreenerScoreResult,
    target_v2_list_type: str,
    target_screener_score: int,
    quality_penalty_applied: bool,
    quality_note: Optional[str],
) -> ScreenerFactorSnapshot:
    """Write composite score and decision summary back to the screener factor snapshot."""

    quality_penalty_weight = None
    if score_result.screener_score > 0:
        quality_penalty_weight = round(target_screener_score / score_result.screener_score, 4)

    quality_flags: list[str] = []
    if quality_penalty_applied:
        quality_flags.append("quality_penalty_applied")
    if quality_note:
        quality_flags.append(quality_note)

    updated_snapshot = screener_factor_snapshot.model_copy(
        update={
            "composite_score": ScreenerCompositeScore(
                screener_score=target_screener_score,
                alpha_score=score_result.alpha_score,
                trigger_score=score_result.trigger_score,
                risk_score=score_result.risk_score,
                list_type=_to_legacy_list_type(target_v2_list_type),
                v2_list_type=target_v2_list_type,
                action_now=_to_action_now(target_v2_list_type),
                quality_penalty_applied=quality_penalty_applied,
                quality_penalty_weight=quality_penalty_weight,
            ),
            "selection_decision": ScreenerSelectionDecision(
                list_type=_to_legacy_list_type(target_v2_list_type),
                v2_list_type=target_v2_list_type,
                action_now=_to_action_now(target_v2_list_type),
                selection_reasons=score_result.top_positive_factors[:3],
                exclusion_reasons=score_result.top_negative_factors[:3],
                top_positive_factors=score_result.top_positive_factors[:3],
                top_negative_factors=score_result.top_negative_factors[:3],
                risk_notes=score_result.risk_notes[:3],
                short_reason=score_result.short_reason,
                quality_flags=quality_flags,
            ),
        }
    )
    return updated_snapshot


def _classify_v2_list_type(
    *,
    alpha_score: int,
    trigger_score: int,
    risk_score: int,
    screener_score: int,
    technical_snapshot: TechnicalSnapshot,
    trigger_state: str,
    threshold_config: dict[str, Any] | None = None,
) -> str:
    if risk_score >= 75 or (technical_snapshot.trend_state == "down" and alpha_score < 60):
        return "AVOID"

    result: str
    if alpha_score >= 72 and trigger_score >= 68 and risk_score <= 45:
        if trigger_state in {"pullback", "breakout"}:
            result = "READY_TO_BUY"
        else:
            result = "RESEARCH_ONLY"
        return _apply_threshold_bucket_overrides(
            base_v2_list_type=result,
            screener_score=screener_score,
            technical_snapshot=technical_snapshot,
            trigger_state=trigger_state,
            threshold_config=threshold_config,
        )

    if alpha_score >= 60 and risk_score <= 60:
        if trigger_state == "pullback":
            result = "WATCH_PULLBACK"
        elif trigger_state == "breakout":
            result = "WATCH_BREAKOUT"
        else:
            result = "RESEARCH_ONLY"
        return _apply_threshold_bucket_overrides(
            base_v2_list_type=result,
            screener_score=screener_score,
            technical_snapshot=technical_snapshot,
            trigger_state=trigger_state,
            threshold_config=threshold_config,
        )

    if alpha_score >= 50 and technical_snapshot.trend_state != "down" and risk_score <= 68:
        if trigger_state == "pullback":
            result = "WATCH_PULLBACK"
        elif trigger_state == "breakout":
            result = "WATCH_BREAKOUT"
        else:
            result = "RESEARCH_ONLY"
        return _apply_threshold_bucket_overrides(
            base_v2_list_type=result,
            screener_score=screener_score,
            technical_snapshot=technical_snapshot,
            trigger_state=trigger_state,
            threshold_config=threshold_config,
        )

    return "AVOID"


def _build_screener_score(
    alpha_score: int,
    trigger_score: int,
    risk_score: int,
    *,
    factor_weight_config: dict[str, Any] | None = None,
) -> int:
    alpha_weight, trigger_weight, risk_weight = _resolve_screener_score_weights(
        factor_weight_config
    )
    score = (
        alpha_score * alpha_weight
        + trigger_score * trigger_weight
        + (100 - risk_score) * risk_weight
    )
    return _clamp_score(score)


def _score_screener_alpha(snapshot: ScreenerFactorSnapshot) -> int:
    cross_section = snapshot.cross_section_factors
    process = snapshot.process_metrics
    atomic = snapshot.atomic_factors
    components = [
        (cross_section.trend_score_raw, 0.28),
        (_pct_to_score(cross_section.return_20d_rank_pct), 0.18),
        (_pct_to_score(cross_section.trend_score_rank_pct), 0.16),
        (_pct_to_score(cross_section.amount_rank_pct), 0.12),
        (_pct_to_score(cross_section.industry_relative_strength_rank_pct), 0.12),
        (_pct_to_score(cross_section.trend_persistence_5d), 0.08),
        (_pct_to_score(process.close_percentile_60d), 0.06),
    ]
    weighted_sum = 0.0
    total_weight = 0.0
    for value, weight in components:
        if value is None:
            continue
        weighted_sum += value * weight
        total_weight += weight

    base = 50.0 if total_weight == 0 else weighted_sum / total_weight
    if atomic.basic_universe_eligibility is False:
        base -= 18.0
    if atomic.liquidity_pass is False:
        base -= 10.0
    if atomic.trend_state_basic == "up":
        base += 6.0
    elif atomic.trend_state_basic == "down":
        base -= 12.0
    return _clamp_score(base)


def _score_screener_trigger(
    *,
    screener_factor_snapshot: ScreenerFactorSnapshot,
    trigger_state: str,
) -> int:
    atomic = screener_factor_snapshot.atomic_factors
    cross_section = screener_factor_snapshot.cross_section_factors
    process = screener_factor_snapshot.process_metrics

    score = 45.0
    if atomic.near_support:
        score += 18.0
    if atomic.breakout_ready:
        score += 18.0
    if trigger_state == "pullback":
        score += 8.0
    elif trigger_state == "breakout":
        score += 10.0
    if cross_section.breakout_readiness_persistence_5d is not None:
        score += cross_section.breakout_readiness_persistence_5d * 10.0
    if process.distance_to_resistance_pct is not None and process.distance_to_resistance_pct > 8.0:
        score -= 8.0
    return _clamp_score(score)


def _score_screener_risk(
    snapshot: ScreenerFactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
) -> int:
    atomic = snapshot.atomic_factors
    cross_section = snapshot.cross_section_factors

    score = 40.0
    if atomic.is_new_listing_risk:
        score += 20.0
    if atomic.is_st_risk:
        score += 30.0
    if atomic.is_suspended_risk:
        score += 30.0
    if atomic.amount_level_state == "low":
        score += 14.0
    elif atomic.amount_level_state == "high":
        score -= 6.0
    if atomic.atr_pct_state == "high":
        score += 15.0
    elif atomic.atr_pct_state == "low":
        score -= 6.0
    if atomic.range_state == "expanded":
        score += 8.0
    elif atomic.range_state == "compressed":
        score -= 4.0
    if atomic.trend_state_basic == "down":
        score += 12.0
    elif atomic.trend_state_basic == "up":
        score -= 6.0
    if technical_snapshot.volatility_state == "high":
        score += 10.0
    elif technical_snapshot.volatility_state == "low":
        score -= 4.0
    if cross_section.volatility_regime_stability is not None:
        score -= cross_section.volatility_regime_stability * 6.0
    return _clamp_score(score)


def _infer_screener_trigger_state(snapshot: ScreenerFactorSnapshot) -> str:
    atomic = snapshot.atomic_factors
    if atomic.near_support:
        return "pullback"
    if atomic.breakout_ready:
        return "breakout"
    return "neutral"


@dataclass(frozen=True)
class _ReasonSummary:
    top_positive_factors: list[str]
    top_negative_factors: list[str]
    risk_notes: list[str]
    short_reason: str


def _build_screener_reason_summary(
    *,
    screener_factor_snapshot: ScreenerFactorSnapshot,
    v2_list_type: str,
    trigger_state: str,
) -> _ReasonSummary:
    atomic = screener_factor_snapshot.atomic_factors
    cross_section = screener_factor_snapshot.cross_section_factors

    positives: list[str] = []
    negatives: list[str] = []
    risks: list[str] = []

    if atomic.close_above_ma20 and atomic.close_above_ma60:
        positives.append("价格站上中期均线")
    if atomic.ma20_above_ma60:
        positives.append("短中期均线多头排列")
    if _is_high_pct(cross_section.return_20d_rank_pct):
        positives.append("20日相对收益位于批次前列")
    if _is_high_pct(cross_section.amount_rank_pct):
        positives.append("成交额处于批次高位")
    if _is_high_pct(cross_section.industry_relative_strength_rank_pct):
        positives.append("行业相对强弱处于领先")
    if atomic.near_support:
        positives.append("价格接近支撑位")
    if atomic.breakout_ready:
        positives.append("价格接近突破触发区")

    if atomic.trend_state_basic == "down":
        negatives.append("趋势结构偏弱")
    if atomic.amount_level_state == "low":
        negatives.append("流动性偏弱")
    if atomic.atr_pct_state == "high":
        negatives.append("短期波动偏高")
    if atomic.is_new_listing_risk:
        negatives.append("上市时间较短")
    if atomic.is_st_risk:
        negatives.append("存在ST风险")
    if atomic.is_suspended_risk:
        negatives.append("存在停牌风险")

    if atomic.is_new_listing_risk:
        risks.append("新股阶段波动与样本稳定性不足")
    if atomic.atr_pct_state == "high":
        risks.append("波动放大时需下调仓位或等待确认")
    if atomic.amount_level_state == "low":
        risks.append("流动性不足时不宜直接作为高优先候选")

    short_reason = _build_screener_short_reason(
        v2_list_type=v2_list_type,
        trigger_state=trigger_state,
        positives=positives,
        negatives=negatives,
    )
    return _ReasonSummary(
        top_positive_factors=positives[:3],
        top_negative_factors=negatives[:3],
        risk_notes=risks[:3],
        short_reason=short_reason,
    )


def _build_screener_short_reason(
    *,
    v2_list_type: str,
    trigger_state: str,
    positives: list[str],
    negatives: list[str],
) -> str:
    if v2_list_type == "READY_TO_BUY":
        if trigger_state == "pullback":
            return "趋势与强度较优，且位置接近支撑，可作为回踩型候选。"
        if trigger_state == "breakout":
            return "趋势与强度较优，且接近突破位，可作为突破型候选。"
        return "趋势与强度较优，但仍建议先进入研究确认。"
    if v2_list_type == "WATCH_PULLBACK":
        return "趋势尚可，适合等待回踩确认后再观察。"
    if v2_list_type == "WATCH_BREAKOUT":
        return "趋势尚可，适合等待突破确认后再观察。"
    if v2_list_type == "RESEARCH_ONLY":
        return "结构有亮点，但仍需结合更多研究信息确认。"
    if negatives:
        return f"当前不纳入优先候选，主要受{negatives[0]}影响。"
    return "当前不纳入优先候选。"


def _pct_to_score(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(100.0, value * 100.0))


def _is_high_pct(value: Optional[float], threshold: float = 0.7) -> bool:
    return value is not None and value >= threshold


def _to_legacy_list_type(v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "BUY_CANDIDATE"
    if v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}:
        return "WATCHLIST"
    return "AVOID"


def _to_action_now(v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "BUY_NOW"
    if v2_list_type == "WATCH_PULLBACK":
        return "WAIT_PULLBACK"
    if v2_list_type == "WATCH_BREAKOUT":
        return "WAIT_BREAKOUT"
    if v2_list_type == "RESEARCH_ONLY":
        return "RESEARCH_ONLY"
    return "AVOID"


def _estimate_legacy_risk_score(snapshot: TechnicalSnapshot) -> int:
    score = 50.0
    if snapshot.volatility_state == "high":
        score += 18.0
    elif snapshot.volatility_state == "low":
        score -= 12.0
    if snapshot.trend_state == "down":
        score += 12.0
    elif snapshot.trend_state == "up":
        score -= 8.0
    return _clamp_score(score)


def _infer_legacy_trigger_state(snapshot: TechnicalSnapshot) -> str:
    support_distance_pct = None
    if snapshot.support_level is not None and snapshot.support_level > 0:
        support_distance_pct = (
            (snapshot.latest_close - snapshot.support_level) / snapshot.support_level * 100.0
        )
        if 0.0 <= support_distance_pct <= 4.0:
            return "pullback"

    resistance_distance_pct = None
    if snapshot.resistance_level is not None and snapshot.latest_close > 0:
        resistance_distance_pct = (
            (snapshot.resistance_level - snapshot.latest_close)
            / snapshot.latest_close
            * 100.0
        )
        if 0.0 <= resistance_distance_pct <= 2.5:
            return "breakout"

    return "neutral"


def _build_legacy_short_reason(snapshot: TechnicalSnapshot, v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "趋势与位置较优，具备进一步跟踪买点的基础条件。"
    if v2_list_type == "WATCH_PULLBACK":
        return "趋势尚可，价格更适合等待回踩确认后再观察。"
    if v2_list_type == "WATCH_BREAKOUT":
        return "趋势尚可，价格更适合等待突破确认后再观察。"
    if v2_list_type == "RESEARCH_ONLY":
        return "因子强弱有分化，先进入研究观察而非直接交易候选。"
    if snapshot.trend_state == "down":
        return "趋势偏弱，当前不适合作为优先候选。"
    return "价格结构或风险约束不满足，暂不纳入候选。"


def _clamp_score(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _resolve_screener_score_weights(
    factor_weight_config: dict[str, Any] | None,
) -> tuple[float, float, float]:
    default_weights = (0.55, 0.30, 0.15)
    if not isinstance(factor_weight_config, dict):
        return default_weights

    alpha_weight = _float_or_none(
        factor_weight_config.get("alpha_weight", factor_weight_config.get("alpha"))
    )
    trigger_weight = _float_or_none(
        factor_weight_config.get("trigger_weight", factor_weight_config.get("trigger"))
    )
    risk_weight = _float_or_none(
        factor_weight_config.get("risk_weight", factor_weight_config.get("risk"))
    )
    if alpha_weight is None or trigger_weight is None or risk_weight is None:
        return default_weights
    if alpha_weight < 0 or trigger_weight < 0 or risk_weight < 0:
        return default_weights
    weight_sum = alpha_weight + trigger_weight + risk_weight
    if weight_sum <= 0:
        return default_weights
    return (
        alpha_weight / weight_sum,
        trigger_weight / weight_sum,
        risk_weight / weight_sum,
    )


def _apply_threshold_bucket_overrides(
    *,
    base_v2_list_type: str,
    screener_score: int,
    technical_snapshot: TechnicalSnapshot,
    trigger_state: str,
    threshold_config: dict[str, Any] | None,
) -> str:
    if not isinstance(threshold_config, dict):
        return base_v2_list_type

    ready_min_score = _int_or_none(threshold_config.get("ready_min_score"))
    watch_min_score = _int_or_none(threshold_config.get("watch_min_score"))
    research_min_score = _int_or_none(threshold_config.get("research_min_score"))

    result = base_v2_list_type
    if (
        result == "READY_TO_BUY"
        and ready_min_score is not None
        and screener_score < ready_min_score
    ):
        result = _fallback_watch_bucket(trigger_state)

    if (
        result in {"WATCH_PULLBACK", "WATCH_BREAKOUT"}
        and watch_min_score is not None
        and screener_score < watch_min_score
    ):
        result = "RESEARCH_ONLY"

    if (
        result == "RESEARCH_ONLY"
        and research_min_score is not None
        and screener_score < research_min_score
        and technical_snapshot.trend_state == "down"
    ):
        result = "AVOID"

    return result


def _fallback_watch_bucket(trigger_state: str) -> str:
    if trigger_state == "pullback":
        return "WATCH_PULLBACK"
    if trigger_state == "breakout":
        return "WATCH_BREAKOUT"
    return "RESEARCH_ONLY"


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
