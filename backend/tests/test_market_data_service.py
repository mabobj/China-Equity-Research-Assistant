"""Tests for the market data service layer."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.db.market_data_store import DATASET_DAILY_BARS, LocalMarketDataStore
from app.schemas.market_data import DailyBar, IntradayBar, StockProfile, UniverseItem
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
