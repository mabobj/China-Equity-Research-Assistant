"""选股评分与兼容分桶规则。"""

from dataclasses import dataclass

from app.schemas.factor import FactorSnapshot
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
    v2_list_type = _classify_v2_list_type(
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        technical_snapshot=snapshot,
        trigger_state=trigger_state,
    )

    return ScreenerScoreResult(
        screener_score=_build_screener_score(alpha_score, trigger_score, risk_score),
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
    alpha_score = factor_snapshot.alpha_score.total_score
    trigger_score = factor_snapshot.trigger_score.total_score
    risk_score = factor_snapshot.risk_score.total_score
    v2_list_type = _classify_v2_list_type(
        alpha_score=alpha_score,
        trigger_score=trigger_score,
        risk_score=risk_score,
        technical_snapshot=technical_snapshot,
        trigger_state=factor_snapshot.trigger_score.trigger_state,
    )
    reasons = build_reason_summary(factor_snapshot)

    return ScreenerScoreResult(
        screener_score=_build_screener_score(alpha_score, trigger_score, risk_score),
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


def _classify_v2_list_type(
    *,
    alpha_score: int,
    trigger_score: int,
    risk_score: int,
    technical_snapshot: TechnicalSnapshot,
    trigger_state: str,
) -> str:
    if risk_score >= 75 or (technical_snapshot.trend_state == "down" and alpha_score < 60):
        return "AVOID"

    if alpha_score >= 72 and trigger_score >= 68 and risk_score <= 45:
        if trigger_state in {"pullback", "breakout"}:
            return "READY_TO_BUY"
        return "RESEARCH_ONLY"

    if alpha_score >= 60 and risk_score <= 60:
        if trigger_state == "pullback":
            return "WATCH_PULLBACK"
        if trigger_state == "breakout":
            return "WATCH_BREAKOUT"
        return "RESEARCH_ONLY"

    if alpha_score >= 50 and technical_snapshot.trend_state != "down" and risk_score <= 68:
        if trigger_state == "pullback":
            return "WATCH_PULLBACK"
        if trigger_state == "breakout":
            return "WATCH_BREAKOUT"
        return "RESEARCH_ONLY"

    return "AVOID"


def _build_screener_score(alpha_score: int, trigger_score: int, risk_score: int) -> int:
    score = alpha_score * 0.55 + trigger_score * 0.30 + (100 - risk_score) * 0.15
    return _clamp_score(score)


def _to_legacy_list_type(v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "BUY_CANDIDATE"
    if v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}:
        return "WATCHLIST"
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
