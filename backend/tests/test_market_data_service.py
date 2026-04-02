"""Tests for the market data service layer."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.db.market_data_store import DATASET_DAILY_BARS, LocalMarketDataStore
from app.schemas.market_data import DailyBar, IntradayBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_products.freshness import resolve_last_closed_trading_day


class FakeProvider:
    """Simple fake provider for unit tests."""

    def __init__(self) -> None:
        self.name = "fake"
        self.profile_symbol: Optional[str] = None
        self.bar_symbol: Optional[str] = None
        self.bar_start_date: Optional[date] = None
        self.bar_end_date: Optional[date] = None
        self.intraday_symbol: Optional[str] = None
        self.intraday_frequency: Optional[str] = None
        self.intraday_start_datetime: Optional[datetime] = None
        self.intraday_end_datetime: Optional[datetime] = None
        self.profile_call_count = 0
        self.daily_bar_call_count = 0
        self.intraday_call_count = 0

    def is_available(self) -> bool:
        return True

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        self.profile_call_count += 1
        self.profile_symbol = symbol
        return StockProfile(
            symbol=symbol,
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            source=self.name,
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        self.daily_bar_call_count += 1
        self.bar_symbol = symbol
        self.bar_start_date = start_date
        self.bar_end_date = end_date
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.5,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                source=self.name,
            ),
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 3),
                open=101.0,
                high=103.0,
                low=100.0,
                close=102.0,
                volume=1200.0,
                amount=120000.0,
                source=self.name,
            ),
        ]

    def get_stock_universe(self) -> list[UniverseItem]:
        return [
            UniverseItem(
                symbol="600519.SH",
                code="600519",
                exchange="SH",
                name="Kweichow Moutai",
                source=self.name,
            )
        ]

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[IntradayBar]:
        self.intraday_call_count += 1
        self.intraday_symbol = symbol
        self.intraday_frequency = frequency
        self.intraday_start_datetime = start_datetime
        self.intraday_end_datetime = end_datetime
        bars = [
            IntradayBar(
                symbol=symbol,
                trade_datetime=datetime(2024, 1, 2, 9, 31, 0),
                frequency=frequency,
                close=100.2,
                source=self.name,
            ),
            IntradayBar(
                symbol=symbol,
                trade_datetime=datetime(2024, 1, 2, 9, 35, 0),
                frequency=frequency,
                close=100.8,
                source=self.name,
            ),
        ]
        if limit is not None:
            return bars[-limit:]
        return bars

    def get_stock_announcements(self, *args, **kwargs) -> list:
        return []

    def get_stock_financial_summary(self, symbol: str):
        return None


class BrokenDailyBarProvider(FakeProvider):
    """用于测试 provider 异常兜底。"""

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        raise TypeError("'NoneType' object is not iterable")


class EmptyDailyBarProvider(FakeProvider):
    """用于模拟优先 provider 返回空结果。"""

    def __init__(self) -> None:
        super().__init__()
        self.name = "empty_daily"

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        self.daily_bar_call_count += 1
        self.bar_symbol = symbol
        self.bar_start_date = start_date
        self.bar_end_date = end_date
        return []


class ProfileOnlyProvider:
    name = "profile_only"
    capabilities = ("profile",)

    def __init__(self) -> None:
        self.called_symbol: Optional[str] = None

    def is_available(self) -> bool:
        return True

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        self.called_symbol = symbol
        return StockProfile(
            symbol=symbol,
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            source=self.name,
        )


class DailyOnlyProvider:
    name = "daily_only"
    capabilities = ("daily_bars",)

    def __init__(self) -> None:
        self.called_symbol: Optional[str] = None

    def is_available(self) -> bool:
        return True

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        self.called_symbol = symbol
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.5,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                source=self.name,
            )
        ]


class IntradayOnlyProvider:
    name = "intraday_only"
    capabilities = ("intraday_bars",)

    def __init__(self) -> None:
        self.called_symbol: Optional[str] = None
        self.called_frequency: Optional[str] = None
        self.called_start_datetime: Optional[datetime] = None
        self.called_end_datetime: Optional[datetime] = None

    def is_available(self) -> bool:
        return True

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[IntradayBar]:
        self.called_symbol = symbol
        self.called_frequency = frequency
        self.called_start_datetime = start_datetime
        self.called_end_datetime = end_datetime
        return [
            IntradayBar(
                symbol=symbol,
                trade_datetime=datetime(2024, 1, 2, 9, 31, 0),
                frequency=frequency,
                close=100.2,
                source=self.name,
            )
        ]


class NamedDailyProvider:
    """用于验证默认 provider 优先级。"""

    capabilities = ("daily_bars",)

    def __init__(self, name: str, close: float) -> None:
        self.name = name
        self.close = close
        self.call_count = 0

    def is_available(self) -> bool:
        return True

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        self.call_count += 1
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.0,
                close=self.close,
                volume=10.0,
                amount=1000.0,
                source=self.name,
            )
        ]


class DirtyDailyBarProvider(FakeProvider):
    """用于验证清洗摘要可见性。"""

    def __init__(self) -> None:
        super().__init__()
        self.name = "dirty"

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        self.daily_bar_call_count += 1
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                source=self.name,
            ),
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 3),
                open=100.0,
                high=101.0,
                low=99.0,
                close=-1.0,
                volume=1000.0,
                amount=100000.0,
                source=self.name,
            ),
        ]


class FinancialSummaryProvider(FakeProvider):
    """用于验证财务清洗接入与缓存元数据补齐。"""

    def __init__(self) -> None:
        super().__init__()
        self.name = "financial_provider"
        self.financial_call_count = 0

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        self.financial_call_count += 1
        return FinancialSummary(
            symbol=symbol,
            name="贵州茅台",
            report_period=date(2024, 12, 31),
            revenue=1250000000.0,
            revenue_yoy=0.148,
            net_profit=650000000.0,
            net_profit_yoy=12.0,
            roe=0.186,
            gross_margin=88.2,
            debt_ratio=36.5,
            eps=42.6,
            bps=210.3,
            source="akshare",
        )


class AnnouncementProvider(FakeProvider):
    """用于验证公告清洗链路。"""

    def __init__(self) -> None:
        super().__init__()
        self.name = "cninfo"
        self.announcement_call_count = 0

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        self.announcement_call_count += 1
        return [
            AnnouncementItem(
                symbol=symbol,
                title="  回购股份进展公告 \n",
                publish_date=date(2026, 3, 27),
                announcement_type="other",
                source="CNINFO",
                url="",
            ),
            AnnouncementItem(
                symbol=symbol,
                title="回购股份进展公告",
                publish_date=date(2026, 3, 27),
                announcement_type="other",
                source="cninfo",
                url="https://example.com/notice?id=1",
            ),
            AnnouncementItem(
                symbol=symbol,
                title="2025年年度报告",
                publish_date=date(2026, 3, 26),
                announcement_type="other",
                source="cninfo",
                url=None,
            ),
        ]


def test_service_normalizes_symbol_before_calling_provider() -> None:
    """The service should always use canonical symbols internally."""
    provider = FakeProvider()
    service = MarketDataService(providers=[provider])

    profile = service.get_stock_profile("sh600519")

    assert provider.profile_symbol == "600519.SH"
    assert profile.symbol == "600519.SH"


def test_service_refreshes_partial_cached_profile(tmp_path: Path) -> None:
    """本地 profile 不完整时，应继续向 provider 补全并回写。"""
    provider = FakeProvider()
    latest_trade_date = resolve_last_closed_trading_day()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_stock_profile(
        StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            industry=None,
            list_date=None,
            total_market_cap=None,
            circulating_market_cap=None,
            source="cninfo",
        )
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    profile = service.get_stock_profile("600519.SH")

    assert provider.profile_call_count == 1
    assert profile.source == "fake"


def test_service_parses_date_filters_for_daily_bars() -> None:
    """The service should parse date strings before calling providers."""
    provider = FakeProvider()
    service = MarketDataService(providers=[provider])

    response = service.get_daily_bars(
        symbol="600519",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    assert provider.bar_symbol == "600519.SH"
    assert provider.bar_start_date == date(2024, 1, 1)
    assert provider.bar_end_date == date(2024, 1, 31)
    assert response.count == 2


def test_service_parses_datetime_filters_for_intraday_bars() -> None:
    """The service should parse intraday datetime filters before calling providers."""
    provider = FakeProvider()
    service = MarketDataService(providers=[provider])

    response = service.get_intraday_bars(
        symbol="600519",
        frequency="5m",
        start_datetime="2024-01-02T09:30:00",
        end_datetime="2024-01-02T10:00:00",
        limit=10,
    )

    assert provider.intraday_symbol == "600519.SH"
    assert provider.intraday_frequency == "5m"
    assert provider.intraday_start_datetime == datetime(2024, 1, 2, 9, 30, 0)
    assert provider.intraday_end_datetime == datetime(2024, 1, 2, 10, 0, 0)
    assert response.frequency == "5m"
    assert response.start_datetime == datetime(2024, 1, 2, 9, 30, 0)
    assert response.end_datetime == datetime(2024, 1, 2, 10, 0, 0)
    assert response.count == 2


def test_service_rejects_unsupported_intraday_frequency() -> None:
    """Unsupported minute frequency should return a clear request error."""
    provider = FakeProvider()
    service = MarketDataService(providers=[provider])

    try:
        service.get_intraday_bars(symbol="600519.SH", frequency="15m")
    except Exception as exc:  # noqa: BLE001
        assert "Unsupported intraday frequency" in str(exc)
    else:
        raise AssertionError("Expected invalid intraday frequency error was not raised.")


def test_service_returns_cached_daily_bars_when_range_is_covered(tmp_path: Path) -> None:
    """Covered ranges should be served from local storage first."""
    provider = FakeProvider()
    latest_trade_date = resolve_last_closed_trading_day()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.5,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                source="local",
            )
        ]
    )
    local_store.mark_range_covered(
        DATASET_DAILY_BARS,
        "600519.SH",
        date(2024, 1, 1),
        date(2024, 1, 31),
    )

    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    response = service.get_daily_bars(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    assert provider.daily_bar_call_count == 0
    assert response.count == 1
    assert response.bars[0].source == "local"
    assert response.quality_status == "ok"
    assert response.cleaning_warnings == []
    assert response.dropped_rows == 0
    assert response.dropped_duplicate_rows == 0


def test_service_runs_mootdx_volume_migration_only_once(tmp_path: Path) -> None:
    """mootdx 历史成交量迁移应幂等执行，避免二次放大。"""
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="000001.SZ",
                trade_date=date(2024, 1, 2),
                open=10.0,
                high=10.3,
                low=9.8,
                close=10.1,
                volume=30087.0,
                amount=12345678.0,
                source="mootdx",
            )
        ]
    )
    local_store.mark_range_covered(
        DATASET_DAILY_BARS,
        "000001.SZ",
        date(2024, 1, 2),
        date(2024, 1, 2),
    )

    service = MarketDataService(
        providers=[FakeProvider()],
        local_store=local_store,
    )
    first = service.get_daily_bars(
        symbol="000001.SZ",
        start_date="2024-01-02",
        end_date="2024-01-02",
    )
    assert first.count == 1
    assert first.bars[0].volume == 3008700.0

    second_service = MarketDataService(
        providers=[FakeProvider()],
        local_store=local_store,
    )
    second = second_service.get_daily_bars(
        symbol="000001.SZ",
        start_date="2024-01-02",
        end_date="2024-01-02",
    )
    assert second.count == 1
    assert second.bars[0].volume == 3008700.0


def test_service_merges_remote_daily_bars_into_local_store(tmp_path: Path) -> None:
    """Remote bars should be merged into local storage without duplicate dates."""
    provider = FakeProvider()
    latest_trade_date = resolve_last_closed_trading_day()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=date(2024, 1, 2),
                open=99.0,
                high=101.0,
                low=98.5,
                close=100.5,
                volume=900.0,
                amount=90000.0,
                source="local",
            )
        ]
    )

    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    response = service.get_daily_bars(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-03",
    )

    assert provider.daily_bar_call_count == 1
    assert response.count == 2
    assert [bar.trade_date for bar in response.bars] == [
        date(2024, 1, 2),
        date(2024, 1, 3),
    ]
    assert response.bars[0].source == "fake"

    second_response = service.get_daily_bars(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-03",
    )

    assert provider.daily_bar_call_count == 1
    assert second_response.count == 2


def test_service_skips_remote_daily_bars_when_sync_disabled_and_cache_empty(
    tmp_path: Path,
) -> None:
    """批量场景关闭远端补齐时，无本地缓存也应快速返回而不是触发 provider。"""
    provider = FakeProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    response = service.get_daily_bars(
        symbol="600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-10",
        allow_remote_sync=False,
    )

    assert provider.daily_bar_call_count == 0
    assert response.count == 0
    assert "remote_sync_skipped_no_cache" in response.cleaning_warnings


def test_refresh_daily_bars_initial_sync_uses_lookback_window(tmp_path: Path) -> None:
    """首次补全应使用最近 lookback_days 的窗口。"""
    provider = FakeProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )
    expected_end_date = resolve_last_closed_trading_day()

    inserted_count = service.refresh_daily_bars("600519.SH", lookback_days=30)

    assert inserted_count == 2
    assert provider.bar_symbol == "600519.SH"
    assert provider.bar_end_date == expected_end_date
    assert provider.bar_start_date == expected_end_date - timedelta(days=29)


def test_refresh_daily_bars_skips_when_today_already_synced(tmp_path: Path) -> None:
    """若本地已有今日日线，本次增量补全应直接跳过。"""
    provider = FakeProvider()
    latest_trade_date = resolve_last_closed_trading_day()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=latest_trade_date,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
                amount=100000.0,
                source="local",
            )
        ]
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    inserted_count = service.refresh_daily_bars("600519.SH", lookback_days=30)

    assert inserted_count == 0
    assert provider.daily_bar_call_count == 0


def test_refresh_daily_bars_incremental_sync_uses_next_day_to_today(
    tmp_path: Path,
) -> None:
    """再次补全时，应从本地最新交易日的下一天补到今天。"""
    expected_end_date = resolve_last_closed_trading_day()
    provider = FakeProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    latest_local_trade_date = expected_end_date - timedelta(days=10)
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=latest_local_trade_date,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
                amount=100000.0,
                source="local",
            )
        ]
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    _ = service.refresh_daily_bars("600519.SH", lookback_days=400)

    assert provider.daily_bar_call_count == 1
    assert provider.bar_start_date == latest_local_trade_date + timedelta(days=1)
    assert provider.bar_end_date == expected_end_date


def test_service_wraps_unexpected_provider_daily_bar_error() -> None:
    """provider 的原始异常不应直接泄漏到 service 层。"""
    service = MarketDataService(providers=[BrokenDailyBarProvider()])

    try:
        service.get_daily_bars("600519.SH", start_date="2024-01-01", end_date="2024-01-31")
    except Exception as exc:  # noqa: BLE001
        assert str(exc).startswith(
            "Failed to load daily bars for 600519.SH from data providers.",
        )
        assert "TypeError: 'NoneType' object is not iterable" in str(exc)
    else:
        raise AssertionError("Expected provider failure was not raised.")


def test_service_returns_cached_daily_bars_when_incremental_refresh_fails(
    tmp_path: Path,
) -> None:
    """增量补今日失败时，应优先回退到本地已缓存的日线数据。"""
    empty_provider = EmptyDailyBarProvider()
    broken_provider = BrokenDailyBarProvider()
    latest_trade_date = resolve_last_closed_trading_day() - timedelta(days=1)
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=latest_trade_date,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
                amount=100000.0,
                source="local",
            )
        ]
    )

    service = MarketDataService(
        providers=[empty_provider, broken_provider],
        local_store=local_store,
    )

    response = service.get_daily_bars("600519.SH")

    assert empty_provider.daily_bar_call_count == 1
    assert response.count == 1
    assert response.bars[0].source == "local"
    assert response.quality_status == "ok"
    assert "remote_failed_use_cache" in response.cleaning_warnings


def test_service_remains_compatible_with_split_capability_providers() -> None:
    """拆分 capability 后，service 仍应能组合多个 provider 对外工作。"""
    profile_provider = ProfileOnlyProvider()
    daily_provider = DailyOnlyProvider()
    service = MarketDataService(providers=[profile_provider, daily_provider])

    profile = service.get_stock_profile("600519.SH")
    daily_bars = service.get_daily_bars("600519.SH", start_date="2024-01-01")

    assert profile.symbol == "600519.SH"
    assert profile_provider.called_symbol == "600519.SH"
    assert daily_provider.called_symbol == "600519.SH"
    assert daily_bars.count == 1


def test_service_supports_split_intraday_provider() -> None:
    """拆分 capability 后，分钟线 provider 应可独立接入 service。"""
    intraday_provider = IntradayOnlyProvider()
    service = MarketDataService(providers=[intraday_provider])

    response = service.get_intraday_bars(
        "600519.SH",
        frequency="1m",
        start_datetime="2024-01-02T09:30:00",
        end_datetime="2024-01-02T09:40:00",
    )

    assert intraday_provider.called_symbol == "600519.SH"
    assert intraday_provider.called_frequency == "1m"
    assert intraday_provider.called_start_datetime == datetime(2024, 1, 2, 9, 30, 0)
    assert intraday_provider.called_end_datetime == datetime(2024, 1, 2, 9, 40, 0)
    assert response.count == 1


def test_service_daily_bars_prefers_mootdx_by_default() -> None:
    """未显式指定时，日线默认优先 mootdx。"""
    akshare_provider = NamedDailyProvider(name="akshare", close=100.5)
    baostock_provider = NamedDailyProvider(name="baostock", close=100.6)
    mootdx_provider = NamedDailyProvider(name="mootdx", close=100.7)
    service = MarketDataService(
        providers=[akshare_provider, baostock_provider, mootdx_provider],
    )

    response = service.get_daily_bars("600519.SH", start_date="2024-01-01")

    assert response.count == 1
    assert response.bars[0].source == "mootdx"
    assert response.bars[0].close == 100.7
    assert mootdx_provider.call_count == 1
    assert baostock_provider.call_count == 0
    assert akshare_provider.call_count == 0


def test_service_daily_bars_exposes_cleaning_summary() -> None:
    """清洗剔除异常行时，应在响应中暴露摘要字段。"""
    service = MarketDataService(providers=[DirtyDailyBarProvider()])

    response = service.get_daily_bars(
        "600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    assert response.count == 1
    assert response.quality_status == "failed"
    assert response.dropped_rows == 1
    assert any("invalid_close_price" in item for item in response.cleaning_warnings)


def test_service_financial_summary_runs_cleaning_and_sets_runtime_fields() -> None:
    """财务摘要应走清洗层，并补齐质量与运行可见字段。"""
    provider = FinancialSummaryProvider()
    service = MarketDataService(providers=[provider])

    summary = service.get_stock_financial_summary("sh600519")

    assert provider.financial_call_count == 1
    assert summary.symbol == "600519.SH"
    assert summary.report_type == "annual"
    assert summary.quality_status in {"ok", "warning"}
    assert summary.provider_used == "financial_provider"
    assert summary.source_mode == "provider_only"
    assert summary.freshness_mode == "provider_fetch"
    assert summary.as_of_date == resolve_last_closed_trading_day()
    assert summary.roe == 18.6
    assert summary.revenue_yoy is not None
    assert abs(summary.revenue_yoy - 14.8) < 1e-9


def test_service_financial_summary_cache_hit_backfills_quality_fields(tmp_path: Path) -> None:
    """旧缓存缺少质量字段时，返回层应自动补齐真实判定并回补 report_type。"""
    provider = FinancialSummaryProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            revenue=1000000000.0,
            source="legacy_cache",
        )
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    summary = service.get_stock_financial_summary("600519.SH")

    assert provider.financial_call_count == 0
    assert summary.report_type == "q3"
    assert summary.quality_status == "degraded"
    assert summary.cleaning_warnings == []
    assert "revenue_yoy" in summary.missing_fields
    assert "net_profit" in summary.missing_fields
    assert "net_profit_yoy" in summary.missing_fields
    assert "roe" in summary.missing_fields
    assert summary.provider_used == "legacy_cache"
    assert summary.source_mode == "local"
    assert summary.freshness_mode == "cache_preferred"
    assert summary.as_of_date == resolve_last_closed_trading_day()


def test_service_financial_summary_cache_hit_with_key_fields_missing_is_degraded(
    tmp_path: Path,
) -> None:
    """关键财务字段大量缺失时，不应误判为 ok。"""
    provider = FinancialSummaryProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="000001.SZ",
            name="平安银行",
            report_period=date(2025, 9, 30),
            source="legacy_cache",
        )
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    summary = service.get_stock_financial_summary("000001.SZ")

    assert provider.financial_call_count == 0
    assert summary.report_type == "q3"
    assert summary.quality_status == "degraded"
    assert "revenue" in summary.missing_fields
    assert "revenue_yoy" in summary.missing_fields
    assert "net_profit" in summary.missing_fields
    assert "net_profit_yoy" in summary.missing_fields
    assert "roe" in summary.missing_fields


def test_service_financial_summary_with_secondary_metrics_is_warning(tmp_path: Path) -> None:
    """核心字段缺失但替代字段充足时，应降为 warning 而非一律 degraded。"""
    provider = FinancialSummaryProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="000002.SZ",
            name="万科A",
            report_period=date(2025, 9, 30),
            gross_margin=21.8,
            debt_ratio=58.2,
            eps=0.73,
            bps=8.31,
            source="legacy_cache",
        )
    )
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    summary = service.get_stock_financial_summary("000002.SZ")

    assert provider.financial_call_count == 0
    assert summary.report_type == "q3"
    assert summary.quality_status == "warning"
    assert "core_financial_fields_missing_use_secondary_metrics" in summary.cleaning_warnings
    assert "revenue" in summary.missing_fields
    assert "net_profit" in summary.missing_fields
    assert "roe" in summary.missing_fields


def test_service_announcements_runs_cleaning_and_deduplicates() -> None:
    """公告接口应统一走清洗链路并输出去重后的结构化结果。"""
    provider = AnnouncementProvider()
    service = MarketDataService(providers=[provider])

    response = service.get_stock_announcements(
        symbol="600519.SH",
        start_date="2026-03-20",
        end_date="2026-03-30",
        limit=20,
    )

    assert provider.announcement_call_count == 1
    assert response.symbol == "600519.SH"
    assert response.count == 2
    assert response.dropped_duplicate_rows == 1
    assert response.quality_status in {"ok", "warning"}
    assert response.provider_used == "cninfo"
    assert response.source_mode == "provider_only"
    assert response.items[0].title == "回购股份进展公告"
    assert response.items[0].announcement_type == "buyback"
    assert response.items[0].url == "https://example.com/notice?id=1"
    assert response.items[1].announcement_type == "earnings"


def test_service_announcements_cache_hit_keeps_cleaning_metadata(tmp_path: Path) -> None:
    """缓存命中路径应继续保留公告清洗摘要字段。"""
    provider = AnnouncementProvider()
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    service = MarketDataService(
        providers=[provider],
        local_store=local_store,
    )

    first_response = service.get_stock_announcements(
        symbol="600519.SH",
        start_date="2026-03-20",
        end_date="2026-03-30",
        limit=20,
    )
    second_response = service.get_stock_announcements(
        symbol="600519.SH",
        start_date="2026-03-20",
        end_date="2026-03-30",
        limit=20,
    )

    assert provider.announcement_call_count == 1
    assert first_response.count == 2
    assert second_response.count == 2
    assert second_response.source_mode == "local_cache"
    assert second_response.quality_status in {"ok", "warning"}
    assert second_response.as_of_date is not None
    assert second_response.dropped_duplicate_rows == 0
    assert second_response.items[0].announcement_type in {"buyback", "earnings", "other"}
