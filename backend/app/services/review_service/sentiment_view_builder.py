"""构建情绪画像。"""

from __future__ import annotations

from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import SentimentView
from app.schemas.technical import TechnicalSnapshot


def build_sentiment_view(
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> SentimentView:
    """基于相对强弱、量能与关键位置构建轻量情绪画像。"""
    sentiment_bias = _resolve_sentiment_bias(
        factor_snapshot=factor_snapshot,
        technical_snapshot=technical_snapshot,
        trigger_snapshot=trigger_snapshot,
    )
    crowding_hint = _build_crowding_hint(
        factor_snapshot=factor_snapshot,
        technical_snapshot=technical_snapshot,
        trigger_snapshot=trigger_snapshot,
    )
    momentum_context = _build_momentum_context(
        factor_snapshot=factor_snapshot,
        technical_snapshot=technical_snapshot,
    )

    return SentimentView(
        sentiment_bias=sentiment_bias,
        crowding_hint=crowding_hint,
        momentum_context=momentum_context,
        concise_summary="{bias}；{momentum}；{crowding}".format(
            bias=_sentiment_bias_label(sentiment_bias),
            momentum=momentum_context,
            crowding=crowding_hint,
        ),
    )


def _resolve_sentiment_bias(
    *,
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> str:
    if technical_snapshot.trend_state == "down" or factor_snapshot.risk_score.total_score >= 70:
        return "bearish"
    if (
        technical_snapshot.trend_state == "up"
        and factor_snapshot.alpha_score.total_score >= 65
        and trigger_snapshot.trigger_state in {"near_support", "near_breakout", "neutral"}
    ):
        return "bullish"
    if (
        technical_snapshot.volatility_state == "high"
        or trigger_snapshot.trigger_state == "overstretched"
        or factor_snapshot.risk_score.total_score >= 55
    ):
        return "cautious"
    return "neutral"


def _build_crowding_hint(
    *,
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> str:
    volume_ratio = technical_snapshot.volume_metrics.volume_ratio_to_ma20
    distance_to_high = factor_snapshot.raw_factors.get("distance_to_52w_high")

    if (
        volume_ratio is not None
        and volume_ratio >= 1.6
        and distance_to_high is not None
        and abs(distance_to_high) <= 0.08
    ):
        return "量能放大且价格接近阶段高位，存在一定拥挤交易迹象。"
    if trigger_snapshot.trigger_state == "near_support":
        return "价格更靠近支撑区，情绪尚未明显拥挤，观察回踩承接更有意义。"
    if technical_snapshot.volatility_state == "high":
        return "波动放大说明短线分歧较强，情绪稳定性一般。"
    return "当前拥挤度信号中性，市场情绪没有出现极端单边。"


def _build_momentum_context(
    *,
    factor_snapshot: FactorSnapshot,
    technical_snapshot: TechnicalSnapshot,
) -> str:
    return_20d = factor_snapshot.raw_factors.get("return_20d")
    return_60d = factor_snapshot.raw_factors.get("return_60d")

    if (return_20d or 0) > 0 and (return_60d or 0) > 0 and technical_snapshot.trend_state == "up":
        return "20 日与 60 日相对强弱均偏正，动量上下文整体向好。"
    if (return_20d or 0) < 0 and technical_snapshot.trend_state == "down":
        return "短中期收益率偏弱，动量上下文对追价并不友好。"
    return "动量读数不算极端，更多需要结合关键价位与触发条件理解。"


def _sentiment_bias_label(sentiment_bias: str) -> str:
    return {
        "bullish": "情绪偏多",
        "neutral": "情绪中性",
        "cautious": "情绪偏谨慎",
        "bearish": "情绪偏空",
    }.get(sentiment_bias, sentiment_bias)
