"""Tests for the local market data store."""

from datetime import date, datetime
from pathlib import Path

import duckdb

from app.db.market_data_store import LocalMarketDataStore
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary


def test_local_store_keeps_multiple_financial_report_periods(tmp_path: Path) -> None:
    """财务数据应按报告期存储，并优先返回最新一期。"""
    store = LocalMarketDataStore(tmp_path / "market.duckdb")

    store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2023, 12, 31),
            revenue=100.0,
            source="fake",
        )
    )
    store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 3, 31),
            revenue=120.0,
            source="fake",
        )
    )

    latest_summary = store.get_stock_financial_summary("600519.SH")

    assert latest_summary is not None
    assert latest_summary.report_period == date(2024, 3, 31)
    assert latest_summary.revenue == 120.0


def test_local_store_migrates_legacy_announcements_table(tmp_path: Path) -> None:
    """旧版公告表应能迁移到新的原子化公告事件表。"""
    database_path = tmp_path / "market.duckdb"
    connection = duckdb.connect(str(database_path))
    connection.execute(
        """
        CREATE TABLE announcements (
            symbol TEXT NOT NULL,
            title TEXT NOT NULL,
            publish_date DATE NOT NULL,
            announcement_type TEXT,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO announcements (
            symbol, title, publish_date, announcement_type, source, url, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "600519.SH",
            "关于年度报告的公告",
            date(2024, 4, 1),
            "定期报告",
            "cninfo",
            (
                "https://www.cninfo.com.cn/new/disclosure/detail"
                "?stockCode=600519&announcementId=123456&orgId=gssh0600519"
            ),
            datetime.utcnow(),
        ],
    )
    connection.close()

    store = LocalMarketDataStore(database_path)
    items = store.get_stock_announcements(
        symbol="600519.SH",
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 1),
        limit=20,
    )

    assert len(items) == 1
    assert items[0] == AnnouncementItem(
        symbol="600519.SH",
        title="关于年度报告的公告",
        publish_date=date(2024, 4, 1),
        announcement_type="定期报告",
        source="cninfo",
        url=(
            "https://www.cninfo.com.cn/new/disclosure/detail"
            "?stockCode=600519&announcementId=123456&orgId=gssh0600519"
        ),
    )


def test_local_store_supports_table_listing_and_readonly_query(tmp_path: Path) -> None:
    """应支持列出表清单并执行只读 SQL 查询。"""
    store = LocalMarketDataStore(tmp_path / "market.duckdb")
    tables = store.list_queryable_tables()
    table_names = {item["table_name"] for item in tables}

    assert "daily_bars" in table_names
    assert "announcement_events" in table_names

    columns, rows = store.execute_readonly_sql(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'",
        limit=5,
    )

    assert columns == ["table_name"]
    assert len(rows) <= 5


def test_local_store_rejects_non_readonly_sql(tmp_path: Path) -> None:
    """非只读 SQL 应被拒绝。"""
    store = LocalMarketDataStore(tmp_path / "market.duckdb")

    try:
        store.execute_readonly_sql("DELETE FROM daily_bars")
    except ValueError as exc:
        assert str(exc) == "Only read-only SQL is allowed."
    else:
        raise AssertionError("Expected non-readonly SQL to be rejected.")


def test_local_store_can_persist_refresh_cursor(tmp_path: Path) -> None:
    """补全游标应可持久化并支持覆盖更新。"""
    store = LocalMarketDataStore(tmp_path / "market.duckdb")

    assert store.get_refresh_cursor("manual_data_refresh_universe_cursor") is None

    store.set_refresh_cursor("manual_data_refresh_universe_cursor", "600519.SH")
    assert store.get_refresh_cursor("manual_data_refresh_universe_cursor") == "600519.SH"

    store.set_refresh_cursor("manual_data_refresh_universe_cursor", "000001.SZ")
    assert store.get_refresh_cursor("manual_data_refresh_universe_cursor") == "000001.SZ"
