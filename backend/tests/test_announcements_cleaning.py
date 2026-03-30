"""公告清洗层测试。"""

from datetime import date, datetime

from app.services.data_service.cleaning.announcements import clean_announcements


def test_clean_announcements_maps_fields_and_deduplicates() -> None:
    """中英文字段映射后应完成去重并优先保留有 URL 的记录。"""
    result = clean_announcements(
        symbol="sh600519",
        rows=[
            {
                "公告标题": "  回购股份进展公告 \n",
                "公告日期": "20260327",
                "公告链接": "",
                "来源": "巨潮资讯",
            },
            {
                "title": "回购股份进展公告",
                "publish_date": "2026-03-27",
                "url": "https://example.com/notice?id=1",
                "source": "cninfo",
            },
            {
                "title": "2025年年度报告",
                "publish_date": "2026/03/26",
                "source": "cninfo",
            },
        ],
        as_of_date=date(2026, 3, 30),
        source_mode="provider_fetch",
    )

    assert result.symbol == "600519.SH"
    assert len(result.items) == 2
    assert result.dropped_duplicate_rows == 1
    assert result.items[0].title == "回购股份进展公告"
    assert result.items[0].url == "https://example.com/notice?id=1"
    assert result.items[0].announcement_type == "buyback"
    assert result.items[1].announcement_type == "earnings"
    assert result.provider_used == "cninfo"


def test_clean_announcements_parses_publish_date_formats() -> None:
    """公告日期支持多种输入格式并统一为 date。"""
    result = clean_announcements(
        symbol="000001.SZ",
        rows=[
            {"title": "风险提示公告", "publish_date": "20260327", "source": "cninfo"},
            {"title": "风险提示公告", "publish_date": "2026/03/27", "source": "cninfo"},
            {"title": "风险提示公告", "publish_date": "2026-03-27", "source": "cninfo"},
            {"title": "风险提示公告", "publish_date": "2026年03月27日", "source": "cninfo"},
            {"title": "风险提示公告", "publish_date": datetime(2026, 3, 27, 15, 10), "source": "cninfo"},
        ],
    )

    assert result.items
    assert result.items[0].publish_date == date(2026, 3, 27)


def test_clean_announcements_marks_failed_when_core_fields_invalid() -> None:
    """标题为空或日期无法解析时应被剔除并返回 failed。"""
    result = clean_announcements(
        symbol="600519.SH",
        rows=[
            {"title": "", "publish_date": "2026-03-27", "source": "cninfo"},
            {"title": "关于事项的公告", "publish_date": "invalid-date", "source": "cninfo"},
        ],
    )

    assert result.items == []
    assert result.quality_status == "failed"
    assert result.dropped_rows == 2
    assert any("missing_title" in warning for warning in result.cleaning_warnings)
    assert any("invalid_publish_date" in warning for warning in result.cleaning_warnings)
