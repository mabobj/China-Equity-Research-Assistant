"""Daily bars daily product."""

from __future__ import annotations

from datetime import date

from app.schemas.market_data import DailyBarResponse
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import DAILY_BARS_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.market_data_service import MarketDataService


class DailyBarsDailyDataset:
    """Resolve daily bars under the daily freshness policy."""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get(
        self,
        symbol: str,
        *,
        as_of_date: date | None = None,
        adjustment_mode: str = "raw",
        force_refresh: bool = False,
        provider_priority: tuple[str, ...] | None = None,
    ) -> DataProductResult[DailyBarResponse]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        response = self._market_data_service.get_daily_bars(
            symbol=symbol,
            end_date=resolved_as_of_date.isoformat(),
            adjustment_mode=adjustment_mode,
            force_refresh=force_refresh,
            provider_names=provider_priority,
        )
        source_mode = "local" if not force_refresh else "local_plus_provider"
        freshness_mode = "force_refreshed" if force_refresh else "cache_preferred"
        return DataProductResult(
            dataset=DAILY_BARS_DAILY,
            symbol=response.symbol,
            as_of_date=resolved_as_of_date,
            payload=response,
            freshness_mode=freshness_mode,
            source_mode=source_mode,
            updated_at=datetime_utcnow(),
        )


def datetime_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
