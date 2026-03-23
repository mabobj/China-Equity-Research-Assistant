"""事件研究器测试。"""

from datetime import date

from app.schemas.research_inputs import AnnouncementItem
from app.services.research_service.event_researcher import EventResearcher


def test_event_researcher_scores_recent_positive_announcements_higher() -> None:
    """近期偏正面的公告应形成更高事件评分。"""
    researcher = EventResearcher()
    announcements = [
        AnnouncementItem(
            symbol="600519.SH",
            title="关于股份回购进展的公告",
            publish_date=date(2024, 3, 20),
            announcement_type="资本运作",
            source="stub",
            url="https://example.com/1",
        ),
        AnnouncementItem(
            symbol="600519.SH",
            title="关于签订重大合作协议的公告",
            publish_date=date(2024, 3, 15),
            announcement_type="重大事项",
            source="stub",
            url="https://example.com/2",
        ),
    ]

    result = researcher.analyze(
        announcements=announcements,
        as_of_date=date(2024, 3, 25),
    )

    assert result.score > 50
    assert any("偏正面" in result.summary or "积极" in result.summary for _ in [0])
    assert len(result.key_reasons) >= 1

