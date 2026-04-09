"""基准目录日级数据产品。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.market_context import BenchmarkCatalogResponse, BenchmarkDefinition
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import BENCHMARK_CATALOG_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date

_DEFAULT_BENCHMARKS = [
    BenchmarkDefinition(
        benchmark_id="sse_composite",
        symbol="000001.SH",
        name="上证指数",
        exchange="SH",
        category="broad_market",
        description="上证主板广义市场基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="sz_component",
        symbol="399001.SZ",
        name="深证成指",
        exchange="SZ",
        category="broad_market",
        description="深市广义市场基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="csi300",
        symbol="000300.SH",
        name="沪深300",
        exchange="SH",
        category="large_cap",
        is_primary=True,
        description="当前默认跨市场主基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="csi500",
        symbol="000905.SH",
        name="中证500",
        exchange="SH",
        category="mid_cap",
        description="中盘风格基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="csi1000",
        symbol="000852.SH",
        name="中证1000",
        exchange="SH",
        category="small_cap",
        description="小盘风格基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="chinext",
        symbol="399006.SZ",
        name="创业板指",
        exchange="SZ",
        category="growth",
        description="创业板成长风格基准。",
    ),
    BenchmarkDefinition(
        benchmark_id="star50",
        symbol="000688.SH",
        name="科创50",
        exchange="SH",
        category="growth",
        description="科创板成长风格基准。",
    ),
]


class BenchmarkCatalogDailyDataset:
    """提供稳定的基准目录。"""

    def get(
        self,
        *,
        as_of_date=None,
    ) -> DataProductResult[BenchmarkCatalogResponse]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        payload = BenchmarkCatalogResponse(
            as_of_date=resolved_as_of_date,
            count=len(_DEFAULT_BENCHMARKS),
            items=list(_DEFAULT_BENCHMARKS),
            source_mode="static_catalog",
            freshness_mode="static",
        )
        return DataProductResult(
            dataset=BENCHMARK_CATALOG_DAILY,
            symbol="__market__",
            as_of_date=resolved_as_of_date,
            payload=payload,
            freshness_mode="static",
            source_mode="static_catalog",
            updated_at=datetime.now(timezone.utc),
        )
