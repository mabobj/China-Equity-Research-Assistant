"""Tests for the market data service layer."""

from datetime import date
from typing import Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.services.data_service.market_data_service import MarketDataService


class FakeProvider:
    """Simple fake provider for unit tests."""

    def __init__(self) -> None:
        self.name = "fake"
        self.profile_symbol: Optional[str] = None
        self.bar_symbol: Optional[str] = None
        self.bar_start_date: Optional[date] = None
        self.bar_end_date: Optional[date] = None

    def is_available(self) -> bool:
        return True

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
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
            )
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


def test_service_normalizes_symbol_before_calling_provider() -> None:
    """The service should always use canonical symbols internally."""
    provider = FakeProvider()
    service = MarketDataService(providers=[provider])

    profile = service.get_stock_profile("sh600519")

    assert provider.profile_symbol == "600519.SH"
    assert profile.symbol == "600519.SH"


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
    assert response.count == 1
