"""Service layer for A-share market data access."""

from datetime import date, datetime
from typing import Optional, Sequence

from app.schemas.market_data import DailyBarResponse, StockProfile, UniverseResponse
from app.services.data_service.exceptions import (
    DataNotFoundError,
    InvalidDateError,
    ProviderError,
)
from app.services.data_service.normalize import normalize_symbol
from app.services.data_service.providers.base import MarketDataProvider


class MarketDataService:
    """High-level market data service with simple provider fallback."""

    def __init__(self, providers: Sequence[MarketDataProvider]) -> None:
        self._providers = list(providers)

    def get_stock_profile(self, symbol: str) -> StockProfile:
        """Return basic stock profile information."""
        canonical_symbol = normalize_symbol(symbol)
        last_error = None

        for provider in self._iter_available_providers():
            try:
                profile = provider.get_stock_profile(canonical_symbol)
            except ProviderError as exc:
                last_error = exc
                continue

            if profile is not None:
                return profile

        if last_error is not None:
            raise ProviderError(
                "Failed to load stock profile for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No stock profile found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        """Return daily bars for one stock."""
        canonical_symbol = normalize_symbol(symbol)
        normalized_start_date = _parse_optional_date(start_date, "start_date")
        normalized_end_date = _parse_optional_date(end_date, "end_date")

        if (
            normalized_start_date is not None
            and normalized_end_date is not None
            and normalized_start_date > normalized_end_date
        ):
            raise InvalidDateError("start_date cannot be later than end_date.")

        last_error = None
        for provider in self._iter_available_providers():
            try:
                bars = provider.get_daily_bars(
                    canonical_symbol,
                    start_date=normalized_start_date,
                    end_date=normalized_end_date,
                )
            except ProviderError as exc:
                last_error = exc
                continue

            if bars:
                return DailyBarResponse(
                    symbol=canonical_symbol,
                    start_date=normalized_start_date,
                    end_date=normalized_end_date,
                    count=len(bars),
                    bars=bars,
                )

        if last_error is not None:
            raise ProviderError(
                "Failed to load daily bars for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No daily bars found for symbol {symbol}.".format(symbol=canonical_symbol),
        )

    def get_stock_universe(self) -> UniverseResponse:
        """Return the basic stock universe."""
        last_error = None

        for provider in self._iter_available_providers():
            try:
                items = provider.get_stock_universe()
            except ProviderError as exc:
                last_error = exc
                continue

            if items:
                return UniverseResponse(count=len(items), items=items)

        if last_error is not None:
            raise ProviderError("Failed to load stock universe from data providers.") from last_error

        raise DataNotFoundError("No stock universe data is currently available.")

    def _iter_available_providers(self) -> list[MarketDataProvider]:
        """Return enabled and available providers."""
        available_providers = [
            provider for provider in self._providers if provider.is_available()
        ]
        if not available_providers:
            raise ProviderError("No enabled market data providers are available.")
        return available_providers


def _parse_optional_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse an optional ISO date string."""
    if value is None or value.strip() == "":
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InvalidDateError(
            "{field_name} must use YYYY-MM-DD format.".format(field_name=field_name),
        ) from exc
