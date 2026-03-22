"""Shared data provider interfaces."""

from typing import Protocol


class MarketDataProvider(Protocol):
    """Minimal protocol for market data providers."""

    def is_available(self) -> bool:
        """Return whether the provider is available."""
