"""事件分析员。"""

from __future__ import annotations

from app.schemas.debate import AnalystView, DebatePoint
from app.schemas.review import EventView


def build_event_analyst_view(event_view: EventView) -> AnalystView:
    """基于事件画像生成事件分析员观点。"""
    positive_points = [
        DebatePoint(title="近期催化", detail=item)
        for item in event_view.recent_catalysts[:3]
    ]
    caution_points = [
        DebatePoint(title="近期风险", detail=item)
        for item in event_view.recent_risks[:3]
    ]

    action_bias = "neutral"
    if event_view.event_temperature in {"hot", "warm"} and positive_points:
        action_bias = "supportive"
    if caution_points and not positive_points:
        action_bias = "negative"
    elif caution_points:
        action_bias = "cautious"

    return AnalystView(
        role="event_analyst",
        summary=event_view.concise_summary,
        action_bias=action_bias,
        positive_points=positive_points,
        caution_points=caution_points,
        key_levels=[],
    )
