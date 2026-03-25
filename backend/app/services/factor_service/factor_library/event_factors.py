"""事件与催化因子。"""

from __future__ import annotations

from datetime import date

from app.schemas.research_inputs import AnnouncementItem
from app.services.factor_service.base import FactorGroupResult, FactorMetric
from app.services.factor_service.preprocess import average_scores, days_between, linear_score

POSITIVE_KEYWORDS = {
    "增持": 3.0,
    "回购": 3.0,
    "中标": 2.5,
    "合同": 2.0,
    "预增": 2.5,
    "分红": 1.5,
    "股权激励": 2.0,
    "并购": 1.5,
}

NEGATIVE_KEYWORDS = {
    "减持": -3.0,
    "问询": -1.5,
    "处罚": -3.0,
    "立案": -3.0,
    "亏损": -2.5,
    "质押": -1.5,
    "诉讼": -2.0,
    "终止": -1.5,
    "风险提示": -2.0,
}


def build_event_group(
    announcements: list[AnnouncementItem],
    *,
    as_of_date: date,
) -> FactorGroupResult:
    """构建事件因子组。"""
    recent_items = [
        item
        for item in announcements
        if 0 <= days_between(as_of_date, item.publish_date) <= 30
    ]
    announcement_count = float(len(recent_items))
    keyword_score = _keyword_score(recent_items)
    freshness_score = _freshness_score(recent_items, as_of_date=as_of_date)

    metrics = [
        FactorMetric(
            factor_name="announcement_count_30d",
            raw_value=announcement_count,
            normalized_score=linear_score(announcement_count, 0.0, 12.0),
            positive_signal="近30日公告较活跃，事件催化关注度较高",
            negative_signal="近30日公告较少，事件催化相对有限",
        ),
        FactorMetric(
            factor_name="announcement_keyword_score",
            raw_value=keyword_score,
            normalized_score=linear_score(keyword_score, -6.0, 6.0),
            positive_signal="近期公告关键词偏正向，存在催化线索",
            negative_signal="近期公告关键词偏谨慎，需关注潜在扰动",
        ),
        FactorMetric(
            factor_name="event_freshness_score",
            raw_value=freshness_score,
            normalized_score=freshness_score,
            positive_signal="近期存在较新的公告催化，事件新鲜度较高",
            negative_signal="近期缺少新的公告催化，事件新鲜度一般",
        ),
    ]

    return FactorGroupResult(
        group_name="event",
        metrics=metrics,
        score=average_scores(metric.normalized_score for metric in metrics),
    )


def _keyword_score(items: list[AnnouncementItem]) -> float:
    score = 0.0
    for item in items:
        title = item.title
        for keyword, weight in POSITIVE_KEYWORDS.items():
            if keyword in title:
                score += weight
        for keyword, weight in NEGATIVE_KEYWORDS.items():
            if keyword in title:
                score += weight
    return score


def _freshness_score(
    items: list[AnnouncementItem],
    *,
    as_of_date: date,
) -> float:
    if not items:
        return 20.0
    newest_days = min(days_between(as_of_date, item.publish_date) for item in items)
    return max(20.0, min(100.0, 100.0 - newest_days * 3.0))
