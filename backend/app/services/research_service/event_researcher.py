"""基于公告列表的规则化事件研究器。"""

from datetime import date

from app.schemas.research import EventResearchResult
from app.schemas.research_inputs import AnnouncementItem

_POSITIVE_KEYWORDS = (
    "回购",
    "增持",
    "中标",
    "签订",
    "分红",
    "业绩预增",
    "增长",
    "激励",
    "通过",
)
_NEGATIVE_KEYWORDS = (
    "减持",
    "问询",
    "监管",
    "风险",
    "诉讼",
    "仲裁",
    "立案",
    "违规",
    "亏损",
    "延期",
    "终止",
    "质押",
)


class EventResearcher:
    """负责将公告列表转换为结构化事件研究结果。"""

    def analyze(
        self,
        announcements: list[AnnouncementItem],
        as_of_date: date,
    ) -> EventResearchResult:
        """分析近期公告并给出第一版事件评分。"""
        score = 50.0
        key_reasons: list[str] = []
        risks: list[str] = []
        triggers: list[str] = []
        invalidations: list[str] = []

        sorted_items = sorted(
            announcements,
            key=lambda item: item.publish_date,
            reverse=True,
        )
        recent_items = [
            item for item in sorted_items if (as_of_date - item.publish_date).days <= 30
        ]
        positive_hits = 0
        negative_hits = 0

        if recent_items:
            score += min(len(recent_items), 5) * 2
            key_reasons.append(
                "近 30 日共有 {count} 条公告，信息更新较及时。".format(
                    count=len(recent_items),
                ),
            )
        else:
            score -= 5
            risks.append("近 30 日公告较少，新增信息驱动不足。")

        for item in sorted_items[:10]:
            title = item.title
            if any(keyword in title for keyword in _POSITIVE_KEYWORDS):
                positive_hits += 1
            if any(keyword in title for keyword in _NEGATIVE_KEYWORDS):
                negative_hits += 1

        if positive_hits > 0:
            score += positive_hits * 6
            key_reasons.append("近期公告中存在偏正面的经营或资本动作。")
            triggers.append("若后续继续出现回购、增持或业绩改善类公告，事件评分可继续改善。")

        if negative_hits > 0:
            score -= negative_hits * 8
            risks.append("近期公告中存在不确定性或偏负面的标题信号。")
            invalidations.append("若问询、减持或诉讼类公告持续增加，事件判断需要转弱。")

        latest_title = sorted_items[0].title if sorted_items else None
        if latest_title is not None:
            triggers.append(
                "重点跟踪最新公告《{title}》后续是否带来实际业绩或治理变化。".format(
                    title=latest_title,
                ),
            )

        final_score = _clamp_score(score)
        summary = _build_summary(
            score=final_score,
            positive_hits=positive_hits,
            negative_hits=negative_hits,
            recent_count=len(recent_items),
        )

        return EventResearchResult(
            score=final_score,
            summary=summary,
            key_reasons=_limit_items(key_reasons, fallback="近期公告以常规披露为主，事件驱动中性。"),
            risks=_limit_items(risks, fallback="公告层面暂无突出事件风险。"),
            triggers=_limit_items(
                triggers,
                fallback="后续关注是否有超预期经营、资本运作或监管事项公告。",
            ),
            invalidations=_limit_items(
                invalidations,
                fallback="若公告出现连续负面事件，当前事件判断需要调整。",
            ),
        )


def _build_summary(
    score: int,
    positive_hits: int,
    negative_hits: int,
    recent_count: int,
) -> str:
    """生成简洁的事件面摘要。"""
    if negative_hits > positive_hits:
        return "近期公告偏谨慎，近 30 日 {count} 条公告中出现更多不确定性信号，事件评分 {score}。".format(
            count=recent_count,
            score=score,
        )
    if positive_hits > 0:
        return "近期公告整体偏中性偏积极，近 30 日 {count} 条公告提供了一定事件支撑，事件评分 {score}。".format(
            count=recent_count,
            score=score,
        )
    return "近期公告以常规披露为主，事件面暂时中性，事件评分 {score}。".format(
        score=score,
    )


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))


def _limit_items(items: list[str], fallback: str) -> list[str]:
    """去重并限制最多返回 3 条。"""
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    if not deduped:
        deduped.append(fallback)
    return deduped[:3]
