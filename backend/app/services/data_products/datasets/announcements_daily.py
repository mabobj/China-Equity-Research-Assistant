"""Announcements daily product."""

from __future__ import annotations

from datetime import timedelta

from app.schemas.research_inputs import AnnouncementListResponse
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import ANNOUNCEMENTS_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.market_data_service import MarketDataService


class AnnouncementsDailyDataset:
    """Resolve recent announcements under the daily freshness policy."""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get(
        self,
        symbol: str,
        *,
        as_of_date=None,
        force_refresh: bool = False,
        lookback_days: int = 30,
        limit: int = 50,
    ) -> DataProductResult[AnnouncementListResponse]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        response = self._market_data_service.get_stock_announcements(
            symbol=symbol,
            start_date=(resolved_as_of_date - timedelta(days=lookback_days)).isoformat(),
            end_date=resolved_as_of_date.isoformat(),
            limit=limit,
            force_refresh=force_refresh,
        )
        return DataProductResult(
            dataset=ANNOUNCEMENTS_DAILY,
            symbol=response.symbol,
            as_of_date=resolved_as_of_date,
            payload=response,
            freshness_mode="force_refreshed" if force_refresh else "cache_preferred",
            source_mode="local_plus_provider" if force_refresh else "local",
            updated_at=datetime_utcnow(),
        )


def datetime_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
