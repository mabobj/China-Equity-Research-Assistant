"""技术分析员。"""

from __future__ import annotations

from app.schemas.debate import AnalystView, DebatePoint
from app.schemas.review import TechnicalView
from app.schemas.intraday import TriggerSnapshot


def build_technical_analyst_view(
    technical_view: TechnicalView,
    trigger_snapshot: TriggerSnapshot,
) -> AnalystView:
    """基于技术画像与触发快照生成技术分析员观点。"""
    positive_points: list[DebatePoint] = []
    caution_points: list[DebatePoint] = []

    if technical_view.trend_state == "up":
        positive_points.append(
            DebatePoint(
                title="趋势状态",
                detail="日线趋势保持上行，说明中短期价格结构仍偏强。",
            )
        )
    if technical_view.trigger_state in {"near_support", "near_breakout"}:
        positive_points.append(
            DebatePoint(
                title="触发位置",
                detail=technical_view.tactical_read,
            )
        )
    if technical_view.trigger_state in {"overstretched", "invalid"}:
        caution_points.append(
            DebatePoint(
                title="位置约束",
                detail=technical_view.tactical_read,
            )
        )
    caution_points.append(
        DebatePoint(
            title="失效条件",
            detail=technical_view.invalidation_hint,
        )
    )

    action_bias = "neutral"
    if technical_view.trend_state == "up" and technical_view.trigger_state in {
        "near_support",
        "near_breakout",
    }:
        action_bias = "supportive"
    elif technical_view.trend_state == "down" or technical_view.trigger_state in {
        "overstretched",
        "invalid",
    }:
        action_bias = "negative"
    elif technical_view.trigger_state == "neutral":
        action_bias = "cautious"

    return AnalystView(
        role="technical_analyst",
        summary="{trend}；{trigger}".format(
            trend="技术趋势偏强" if technical_view.trend_state == "up" else "技术趋势中性或偏弱",
            trigger=trigger_snapshot.trigger_note,
        ),
        action_bias=action_bias,
        positive_points=positive_points[:3],
        caution_points=caution_points[:3],
        key_levels=technical_view.key_levels,
    )
