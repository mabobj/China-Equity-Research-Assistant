"""基准日线按日读取数据产品。"""

from __future__ import annotations

from datetime import timedelta

from app.schemas.market_data import DailyBarResponse
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import BENCHMARK_BARS_DAILY
from app.services.data_products.datasets.benchmark_catalog_daily import _DEFAULT_BENCHMARKS
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.exceptions import InvalidRequestError
from app.services.data_service.market_data_service import MarketDataService


_BENCHMARK_MAP = {item.symbol: item for item in _DEFAULT_BENCHMARKS}


class BenchmarkBarsDailyDataset:
    """基于静态基准目录读取真实按日日线。"""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get(
        self,
        benchmark_symbol: str,
        *,
        as_of_date=None,
        lookback_days: int = 120,
        force_refresh: bool = False,
    ) -> DataProductResult[DailyBarResponse]:
        if benchmark_symbol not in _BENCHMARK_MAP:
            raise InvalidRequestError(
                f"unsupported benchmark symbol: {benchmark_symbol}",
            )
        if lookback_days < 20 or lookback_days > 1000:
            raise InvalidRequestError("lookback_days must be between 20 and 1000.")

        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        start_date = resolved_as_of_date - timedelta(days=lookback_days)
        response = self._market_data_service.get_daily_bars(
            symbol=benchmark_symbol,
            start_date=start_date.isoformat(),
            end_date=resolved_as_of_date.isoformat(),
            force_refresh=force_refresh,
        )
        freshness_mode = "force_refreshed" if force_refresh else "cache_preferred"
        source_mode = "local_plus_provider" if force_refresh else "local_preferred"
        return DataProductResult(
            dataset=BENCHMARK_BARS_DAILY,
            symbol=benchmark_symbol,
            as_of_date=resolved_as_of_date,
            payload=response,
            freshness_mode=freshness_mode,
            source_mode=source_mode,
            updated_at=_datetime_utcnow(),
        )


def _datetime_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
