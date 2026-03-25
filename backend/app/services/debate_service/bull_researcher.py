"""多头研究员。"""

from __future__ import annotations

from app.schemas.debate import AnalystViewsBundle, BullCase, DebatePoint


def build_bull_case(analyst_views: AnalystViewsBundle) -> BullCase:
    """提炼支持交易的最强理由。"""
    reasons: list[DebatePoint] = []
    for analyst_view in (
        analyst_views.technical,
        analyst_views.fundamental,
        analyst_views.event,
        analyst_views.sentiment,
    ):
        if analyst_view.action_bias not in {"supportive", "neutral"}:
            continue
        reasons.extend(analyst_view.positive_points)

    deduped = _dedupe_points(reasons)[:3]
    if not deduped:
        deduped = [
            DebatePoint(
                title="观察结论",
                detail="当前支持交易的理由不够集中，更适合继续跟踪等待更清晰信号。",
            )
        ]

    return BullCase(
        summary="多头研究员认为，若强调可执行性与相对优势，当前最值得关注的是趋势、催化与动量是否继续配合。",
        reasons=deduped,
    )


def _dedupe_points(items: list[DebatePoint]) -> list[DebatePoint]:
    seen: set[tuple[str, str]] = set()
    ordered: list[DebatePoint] = []
    for item in items:
        key = (item.title, item.detail)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered
