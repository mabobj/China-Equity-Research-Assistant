"""构建事件画像。"""

from __future__ import annotations

from app.schemas.factor import FactorSnapshot
from app.schemas.research_inputs import AnnouncementItem
from app.schemas.review import EventView
from app.services.factor_service.factor_library.event_factors import (
    NEGATIVE_KEYWORDS,
    POSITIVE_KEYWORDS,
)


def build_event_view(
    announcements: list[AnnouncementItem],
    factor_snapshot: FactorSnapshot,
) -> EventView:
    """基于公告与事件因子构建事件画像。"""
    recent_catalysts = _collect_titles(announcements, keyword_weights=POSITIVE_KEYWORDS)
    recent_risks = _collect_titles(announcements, keyword_weights=NEGATIVE_KEYWORDS)
    event_group_score = _get_event_group_score(factor_snapshot)
    event_temperature = _resolve_event_temperature(event_group_score)

    if announcements:
        summary = "近 30 日共跟踪到 {count} 条公告，事件热度为 {temperature}。".format(
            count=len(announcements),
            temperature=_event_temperature_label(event_temperature),
        )
    else:
        summary = "近 30 日未获取到明确公告催化，事件面更多保持中性观察。"

    if recent_catalysts:
        summary += " 正向线索包括: {items}。".format(items="；".join(recent_catalysts[:2]))
    if recent_risks:
        summary += " 需要留意的扰动包括: {items}。".format(items="；".join(recent_risks[:2]))

    return EventView(
        recent_catalysts=recent_catalysts[:3],
        recent_risks=recent_risks[:3],
        event_temperature=event_temperature,
        concise_summary=summary,
    )


def _collect_titles(
    announcements: list[AnnouncementItem],
    *,
    keyword_weights: dict[str, float],
) -> list[str]:
    matched_titles: list[str] = []
    for item in announcements:
        if any(keyword in item.title for keyword in keyword_weights):
            matched_titles.append(item.title)
    return matched_titles


def _get_event_group_score(factor_snapshot: FactorSnapshot) -> float | None:
    for group in factor_snapshot.factor_group_scores:
        if group.group_name == "event":
            return group.score
    return None


def _resolve_event_temperature(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 70:
        return "hot"
    if score >= 55:
        return "warm"
    if score >= 40:
        return "neutral"
    return "cool"


def _event_temperature_label(temperature: str) -> str:
    return {
        "hot": "偏热",
        "warm": "偏暖",
        "neutral": "中性",
        "cool": "偏冷",
    }.get(temperature, temperature)
