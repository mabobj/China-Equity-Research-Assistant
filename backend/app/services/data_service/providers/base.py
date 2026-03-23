"""Shared data provider interfaces."""

from datetime import date
from typing import Optional, Protocol

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem


class MarketDataProvider(Protocol):
    """Minimal protocol for market data providers."""

    name: str

    def is_available(self) -> bool:
        """Return whether the provider is available."""

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """Return the basic profile for one stock."""

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """Return daily bars for one stock."""

    def get_stock_universe(self) -> list[UniverseItem]:
        """Return the basic A-share stock universe."""
