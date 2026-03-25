"""情绪分析员。"""

from __future__ import annotations

from app.schemas.debate import AnalystView, DebatePoint
from app.schemas.review import SentimentView


def build_sentiment_analyst_view(sentiment_view: SentimentView) -> AnalystView:
    """基于情绪画像生成情绪分析员观点。"""
    positive_points: list[DebatePoint] = []
    caution_points: list[DebatePoint] = []

    if sentiment_view.sentiment_bias == "bullish":
        positive_points.append(
            DebatePoint(title="市场偏好", detail="市场偏好仍偏向强势方向。")
        )
    elif sentiment_view.sentiment_bias in {"cautious", "bearish"}:
        caution_points.append(
            DebatePoint(title="市场偏好", detail=sentiment_view.concise_summary)
        )

    positive_points.append(
        DebatePoint(title="动量环境", detail=sentiment_view.momentum_context)
    )
    caution_points.append(
        DebatePoint(title="拥挤度提示", detail=sentiment_view.crowding_hint)
    )

    action_bias = "neutral"
    if sentiment_view.sentiment_bias == "bullish":
        action_bias = "supportive"
    elif sentiment_view.sentiment_bias == "bearish":
        action_bias = "negative"
    elif sentiment_view.sentiment_bias == "cautious":
        action_bias = "cautious"

    return AnalystView(
        role="sentiment_analyst",
        summary=sentiment_view.concise_summary,
        action_bias=action_bias,
        positive_points=positive_points[:3],
        caution_points=caution_points[:3],
        key_levels=[],
    )
