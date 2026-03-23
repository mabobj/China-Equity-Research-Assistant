"""选股器评分规则。"""

from dataclasses import dataclass
from typing import Optional

from app.schemas.technical import TechnicalSnapshot


@dataclass(frozen=True)
class ScreenerScoreResult:
    """选股评分结果。"""

    screener_score: int
    list_type: str
    short_reason: str


def score_technical_snapshot(snapshot: TechnicalSnapshot) -> ScreenerScoreResult:
    """根据技术快照生成选股评分和分桶。"""
    score = float(snapshot.trend_score)

    if snapshot.trend_state == "up":
        score += 10
    elif snapshot.trend_state == "down":
        score -= 18

    if snapshot.volatility_state == "low":
        score += 4
    elif snapshot.volatility_state == "high":
        score -= 10

    ma20 = snapshot.moving_averages.ma20
    if ma20 is not None:
        if snapshot.latest_close >= ma20:
            score += 6
        else:
            score -= 8

    volume_ratio = snapshot.volume_metrics.volume_ratio_to_ma20
    if volume_ratio is not None:
        if volume_ratio >= 1.1:
            score += 6
        elif volume_ratio < 0.8:
            score -= 5

    support_distance = None
    if snapshot.support_level is not None and snapshot.support_level > 0:
        support_distance = (
            snapshot.latest_close - snapshot.support_level
        ) / snapshot.support_level
        if snapshot.latest_close < snapshot.support_level:
            score -= 12
        elif support_distance <= 0.05:
            score += 4

    resistance_distance = None
    if snapshot.resistance_level is not None and snapshot.latest_close > 0:
        resistance_distance = (
            snapshot.resistance_level - snapshot.latest_close
        ) / snapshot.latest_close
        if 0 <= resistance_distance <= 0.03 and snapshot.trend_state == "up":
            score += 5

    final_score = _clamp_score(score)
    list_type = _determine_list_type(final_score, snapshot)
    short_reason = _build_short_reason(
        snapshot=snapshot,
        list_type=list_type,
        support_distance=support_distance,
        resistance_distance=resistance_distance,
    )

    return ScreenerScoreResult(
        screener_score=final_score,
        list_type=list_type,
        short_reason=short_reason,
    )


def _determine_list_type(score: int, snapshot: TechnicalSnapshot) -> str:
    """根据评分和趋势状态分桶。"""
    if score >= 75 and snapshot.trend_state == "up":
        return "BUY_CANDIDATE"
    if score >= 50 and snapshot.trend_state != "down":
        return "WATCHLIST"
    return "AVOID"


def _build_short_reason(
    snapshot: TechnicalSnapshot,
    list_type: str,
    support_distance: Optional[float],
    resistance_distance: Optional[float],
) -> str:
    """生成模板化短理由。"""
    if list_type == "BUY_CANDIDATE":
        if resistance_distance is not None and resistance_distance <= 0.03:
            return "上行趋势延续，价格接近突破位，量能结构尚可。"
        if support_distance is not None and support_distance <= 0.05:
            return "上行趋势未破坏，价格靠近支撑区，具备回踩观察价值。"
        return "趋势分数较高，价格结构与量能表现偏强。"

    if list_type == "WATCHLIST":
        if snapshot.volatility_state == "high":
            return "趋势尚可，但波动偏大，先列入观察名单。"
        return "技术结构中性偏强，等待更清晰的突破或回踩确认。"

    if snapshot.trend_state == "down":
        return "趋势偏弱，当前不适合作为优先候选。"
    return "价格结构或流动性支撑不足，暂不考虑纳入候选。"


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))
