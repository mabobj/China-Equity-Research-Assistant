from datetime import date

from app.services.data_service.providers.cninfo_provider import CninfoProvider


def test_cninfo_provider_maps_financial_report_indexes(monkeypatch) -> None:
    provider = CninfoProvider()
    monkeypatch.setattr(
        "app.services.data_service.providers.cninfo_provider._get_cninfo_org_id_map",
        lambda: {"600519": "gssz0000001"},
    )
    monkeypatch.setattr(
        provider,
        "_query_announcements",
        lambda **kwargs: [
            {
                "announcementTitle": "2025年年度报告",
                "announcementTime": "2026-03-28 18:00:00",
                "announcementId": "123456",
                "orgId": "gssz0000001",
            }
        ],
    )

    items = provider.get_financial_report_indexes("600519.SH", limit=10)

    assert len(items) == 1
    assert items[0].symbol == "600519.SH"
    assert items[0].report_period == date(2025, 12, 31)
    assert items[0].report_type == "annual"
    assert items[0].publish_date == date(2026, 3, 28)
    assert items[0].url.endswith("announcementId=123456&orgId=gssz0000001&announcementTime=2026-03-28")
