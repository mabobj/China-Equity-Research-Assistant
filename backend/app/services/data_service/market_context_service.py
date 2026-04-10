"""关键市场数据域读取服务。"""

from __future__ import annotations

from datetime import datetime

from app.schemas.market_context import (
    BenchmarkCatalogResponse,
    MarketBreadthSnapshot,
    RiskProxySnapshot,
    StockClassificationSnapshot,
)
from app.services.data_products.datasets.benchmark_catalog_daily import (
    BenchmarkCatalogDailyDataset,
)
from app.services.data_products.datasets.benchmark_bars_daily import (
    BenchmarkBarsDailyDataset,
)
from app.services.data_products.datasets.industry_classification_daily import (
    IndustryClassificationDailyDataset,
)
from app.services.data_products.datasets.market_breadth_daily import (
    MarketBreadthDailyDataset,
)
from app.services.data_products.datasets.risk_proxy_daily import RiskProxyDailyDataset


class MarketContextService:
    """对外提供关键数据域的稳定读取入口。"""

    def __init__(
        self,
        *,
        benchmark_catalog_daily: BenchmarkCatalogDailyDataset,
        benchmark_bars_daily: BenchmarkBarsDailyDataset,
        industry_classification_daily: IndustryClassificationDailyDataset,
        market_breadth_daily: MarketBreadthDailyDataset,
        risk_proxy_daily: RiskProxyDailyDataset,
    ) -> None:
        self._benchmark_catalog_daily = benchmark_catalog_daily
        self._benchmark_bars_daily = benchmark_bars_daily
        self._industry_classification_daily = industry_classification_daily
        self._market_breadth_daily = market_breadth_daily
        self._risk_proxy_daily = risk_proxy_daily

    def get_benchmark_catalog(
        self,
        *,
        as_of_date=None,
    ) -> BenchmarkCatalogResponse:
        return self._benchmark_catalog_daily.get(
            as_of_date=_parse_optional_as_of_date(as_of_date),
        ).payload

    def get_stock_classification(
        self,
        symbol: str,
        *,
        as_of_date=None,
        force_refresh: bool = False,
    ) -> StockClassificationSnapshot:
        return self._industry_classification_daily.get(
            symbol,
            as_of_date=_parse_optional_as_of_date(as_of_date),
            force_refresh=force_refresh,
        ).payload

    def get_benchmark_daily_bars(
        self,
        benchmark_symbol: str,
        *,
        as_of_date=None,
        lookback_days: int = 120,
        force_refresh: bool = False,
    ):
        return self._benchmark_bars_daily.get(
            benchmark_symbol,
            as_of_date=_parse_optional_as_of_date(as_of_date),
            lookback_days=lookback_days,
            force_refresh=force_refresh,
        ).payload

    def get_market_breadth(
        self,
        *,
        as_of_date=None,
        max_symbols: int | None = None,
        force_refresh: bool = False,
    ) -> MarketBreadthSnapshot:
        return self._market_breadth_daily.get(
            as_of_date=_parse_optional_as_of_date(as_of_date),
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        ).payload

    def get_risk_proxy(
        self,
        *,
        as_of_date=None,
        max_symbols: int | None = None,
        force_refresh: bool = False,
    ) -> RiskProxySnapshot:
        return self._risk_proxy_daily.get(
            as_of_date=_parse_optional_as_of_date(as_of_date),
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        ).payload


def _parse_optional_as_of_date(value):
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat"):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()
