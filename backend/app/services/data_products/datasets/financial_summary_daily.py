"""Financial summary daily product."""

from __future__ import annotations

from app.schemas.research_inputs import FinancialSummary
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import FINANCIAL_SUMMARY_DAILY
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_service.market_data_service import MarketDataService


class FinancialSummaryDailyDataset:
    """Resolve financial summary under the daily freshness policy."""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get(
        self,
        symbol: str,
        *,
        force_refresh: bool = False,
    ) -> DataProductResult[FinancialSummary]:
        as_of_date = resolve_last_closed_trading_day()
        payload = self._market_data_service.get_stock_financial_summary(
            symbol,
            force_refresh=force_refresh,
        )
        return DataProductResult(
            dataset=FINANCIAL_SUMMARY_DAILY,
            symbol=payload.symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="force_refreshed" if force_refresh else "cache_preferred",
            source_mode="local_plus_provider" if force_refresh else "local",
            updated_at=datetime_utcnow(),
        )


def datetime_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
