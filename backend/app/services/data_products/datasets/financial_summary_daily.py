"""Financial summary daily product."""

from __future__ import annotations

from app.schemas.research_inputs import FinancialSummary
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import FINANCIAL_SUMMARY_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.market_data_service import MarketDataService


class FinancialSummaryDailyDataset:
    """Resolve financial summary under the daily freshness policy."""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get(
        self,
        symbol: str,
        *,
        as_of_date=None,
        force_refresh: bool = False,
    ) -> DataProductResult[FinancialSummary]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        payload = self._market_data_service.get_stock_financial_summary(
            symbol,
            force_refresh=force_refresh,
        )
        payload_as_of_date = payload.as_of_date or resolved_as_of_date
        freshness_mode = payload.freshness_mode or (
            "force_refreshed" if force_refresh else "cache_preferred"
        )
        source_mode = payload.source_mode or (
            "local_plus_provider" if force_refresh else "local"
        )
        return DataProductResult(
            dataset=FINANCIAL_SUMMARY_DAILY,
            symbol=payload.symbol,
            as_of_date=payload_as_of_date,
            payload=payload,
            freshness_mode=freshness_mode,
            source_mode=source_mode,
            updated_at=datetime_utcnow(),
        )


def datetime_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
