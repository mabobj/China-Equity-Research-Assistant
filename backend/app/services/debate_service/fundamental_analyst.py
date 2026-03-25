"""基本面分析员。"""

from __future__ import annotations

from app.schemas.debate import AnalystView, DebatePoint
from app.schemas.review import FundamentalView


def build_fundamental_analyst_view(
    fundamental_view: FundamentalView,
) -> AnalystView:
    """基于基本面画像生成基本面分析员观点。"""
    positive_points: list[DebatePoint] = []
    caution_points: list[DebatePoint] = []

    if fundamental_view.quality_read is not None:
        target_list = positive_points if "偏弱" not in fundamental_view.quality_read else caution_points
        target_list.append(
            DebatePoint(title="质量判断", detail=fundamental_view.quality_read)
        )
    if fundamental_view.growth_read is not None:
        target_list = positive_points if "拖累" not in fundamental_view.growth_read else caution_points
        target_list.append(
            DebatePoint(title="成长判断", detail=fundamental_view.growth_read)
        )
    for flag in fundamental_view.key_financial_flags:
        if flag != "当前未出现明显财务红旗":
            caution_points.append(DebatePoint(title="财务风险", detail=flag))
    if fundamental_view.leverage_read is not None:
        target_list = positive_points if "偏高" not in fundamental_view.leverage_read else caution_points
        target_list.append(
            DebatePoint(title="杠杆判断", detail=fundamental_view.leverage_read)
        )

    action_bias = "neutral"
    if caution_points and not positive_points:
        action_bias = "negative"
    elif positive_points and not caution_points:
        action_bias = "supportive"
    elif caution_points:
        action_bias = "cautious"

    caution_output = [
        point for point in caution_points if point.title == "财务风险"
    ]
    caution_output.extend(
        point for point in caution_points if point.title != "财务风险"
    )
    caution_output.append(
        DebatePoint(
            title="字段完整度",
            detail=fundamental_view.data_completeness_note,
        )
    )

    return AnalystView(
        role="fundamental_analyst",
        summary="{quality} {growth} {leverage}".format(
            quality=fundamental_view.quality_read or "",
            growth=fundamental_view.growth_read or "",
            leverage=fundamental_view.leverage_read or "",
        ).strip(),
        action_bias=action_bias,
        positive_points=positive_points[:3],
        caution_points=caution_output[:3],
        key_levels=[],
    )
