"""空头研究员。"""

from __future__ import annotations

from app.schemas.debate import AnalystViewsBundle, BearCase, DebatePoint


def build_bear_case(analyst_views: AnalystViewsBundle) -> BearCase:
    """提炼反对交易或建议谨慎的最强理由。"""
    reasons: list[DebatePoint] = []
    for analyst_view in (
        analyst_views.technical,
        analyst_views.fundamental,
        analyst_views.event,
        analyst_views.sentiment,
    ):
        reasons.extend(analyst_view.caution_points)

    deduped = _dedupe_points(reasons)[:3]
    if not deduped:
        deduped = [
            DebatePoint(
                title="风险约束",
                detail="当前没有突出的负面要点，但仍需遵守纪律，避免在证据不足时激进交易。",
            )
        ]

    return BearCase(
        summary="空头研究员认为，短线位置、风险约束和财务或事件扰动仍可能削弱当前交易赔率。",
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
