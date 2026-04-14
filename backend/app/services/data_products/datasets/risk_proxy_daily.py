"""基础风险代理日级数据产品。"""

from __future__ import annotations

from app.schemas.market_context import RiskProxySnapshot
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import RISK_PROXY_DAILY
from app.services.data_products.datasets.benchmark_catalog_daily import (
    BenchmarkCatalogDailyDataset,
)
from app.services.data_products.datasets.benchmark_bars_daily import (
    BenchmarkBarsDailyDataset,
)
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository
from app.services.data_products.datasets.market_breadth_daily import (
    MarketBreadthDailyDataset,
)


class RiskProxyDailyDataset:
    """基于市场广度构建最小风险代理快照。"""

    def __init__(
        self,
        *,
        repository: DataProductRepository,
        benchmark_catalog_daily: BenchmarkCatalogDailyDataset,
        benchmark_bars_daily: BenchmarkBarsDailyDataset,
        market_breadth_daily: MarketBreadthDailyDataset,
    ) -> None:
        self._repository = repository
        self._benchmark_catalog_daily = benchmark_catalog_daily
        self._benchmark_bars_daily = benchmark_bars_daily
        self._market_breadth_daily = market_breadth_daily

    def get(
        self,
        *,
        as_of_date=None,
        max_symbols: int | None = None,
        force_refresh: bool = False,
    ) -> DataProductResult[RiskProxySnapshot]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        params_hash = self._repository.build_params_hash({"max_symbols": max_symbols})
        if not force_refresh:
            cached = self._repository.load(
                dataset=RISK_PROXY_DAILY,
                symbol="__market__",
                as_of_date=resolved_as_of_date,
                params_hash=params_hash,
            )
            if cached is not None:
                payload = RiskProxySnapshot.model_validate(cached.payload)
                return DataProductResult(
                    dataset=RISK_PROXY_DAILY,
                    symbol="__market__",
                    as_of_date=cached.as_of_date,
                    payload=payload,
                    freshness_mode="cache_hit",
                    source_mode="snapshot",
                    updated_at=cached.updated_at,
                    dataset_version=cached.dataset_version,
                    provider_used=cached.provider_used,
                    warning_messages=cached.warning_messages,
                    lineage_metadata=cached.lineage_metadata,
                )

        breadth_result = self._market_breadth_daily.get(
            as_of_date=resolved_as_of_date,
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        )
        breadth = breadth_result.payload
        cross_sectional_volatility = None
        warning_messages = list(breadth.warning_messages)
        benchmark_symbol = None
        benchmark_name = None
        benchmark_close = None
        benchmark_return_1d = None
        benchmark_return_20d = None
        benchmark_trend_state = "unknown"

        # 当前第二版先用广度 + 主基准收益构建保守风险代理。
        if breadth.mean_return_1d is not None and breadth.median_return_1d is not None:
            cross_sectional_volatility = abs(
                breadth.mean_return_1d - breadth.median_return_1d,
            )
        else:
            warning_messages.append("cross_sectional_volatility_proxy_limited")

        breadth_penalty = 100.0 - breadth.breadth_score
        volatility_penalty = 0.0
        benchmark_penalty = 0.0
        if cross_sectional_volatility is not None:
            volatility_penalty = min(cross_sectional_volatility * 18.0, 100.0)

        benchmark_catalog = self._benchmark_catalog_daily.get(
            as_of_date=resolved_as_of_date,
        )
        primary_benchmark = next(
            (item for item in benchmark_catalog.payload.items if item.is_primary),
            None,
        )
        if primary_benchmark is not None:
            benchmark_symbol = primary_benchmark.symbol
            benchmark_name = primary_benchmark.name
            try:
                benchmark_result = self._benchmark_bars_daily.get(
                    benchmark_symbol,
                    as_of_date=resolved_as_of_date,
                    lookback_days=30,
                    force_refresh=force_refresh,
                )
                benchmark_bars = benchmark_result.payload.items
                if benchmark_bars:
                    benchmark_close = benchmark_bars[-1].close
                if len(benchmark_bars) >= 2:
                    benchmark_return_1d = _compute_return_pct(
                        benchmark_bars[-2].close,
                        benchmark_bars[-1].close,
                    )
                if len(benchmark_bars) >= 21:
                    benchmark_return_20d = _compute_return_pct(
                        benchmark_bars[-21].close,
                        benchmark_bars[-1].close,
                    )
                benchmark_trend_state = _infer_trend_state(
                    benchmark_return_1d,
                    benchmark_return_20d,
                )
                benchmark_penalty = _compute_benchmark_penalty(
                    benchmark_return_1d,
                    benchmark_return_20d,
                    benchmark_trend_state,
                )
            except Exception:
                warning_messages.append("primary_benchmark_unavailable_use_breadth_only")
        else:
            warning_messages.append("primary_benchmark_missing_use_breadth_only")

        risk_score = max(
            0.0,
            min(100.0, breadth_penalty * 0.55 + volatility_penalty * 0.15 + benchmark_penalty * 0.30),
        )

        if risk_score >= 67.0:
            risk_regime = "risk_off"
        elif risk_score >= 34.0:
            risk_regime = "neutral"
        else:
            risk_regime = "risk_on"

        quality_status = breadth.quality_status
        payload = RiskProxySnapshot(
            as_of_date=resolved_as_of_date,
            universe_size=breadth.universe_size,
            symbols_considered=breadth.symbols_considered,
            breadth_score=breadth.breadth_score,
            cross_sectional_volatility_1d=cross_sectional_volatility,
            median_return_1d=breadth.median_return_1d,
            primary_benchmark_symbol=benchmark_symbol,
            primary_benchmark_name=benchmark_name,
            benchmark_close=benchmark_close,
            benchmark_return_1d=benchmark_return_1d,
            benchmark_return_20d=benchmark_return_20d,
            benchmark_trend_state=benchmark_trend_state,
            risk_score=risk_score,
            risk_regime=risk_regime,
            quality_status=quality_status,
            warning_messages=list(dict.fromkeys(warning_messages)),
            source_mode=(
                "breadth_plus_benchmark"
                if benchmark_symbol is not None and benchmark_trend_state != "unknown"
                else "derived_from_breadth"
            ),
            freshness_mode="computed",
        )
        entry = self._repository.create_entry(
            dataset=RISK_PROXY_DAILY,
            symbol="__market__",
            as_of_date=resolved_as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode=payload.source_mode,
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=RISK_PROXY_DAILY,
            symbol="__market__",
            as_of_date=resolved_as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode=payload.source_mode,
            updated_at=entry.updated_at,
            dataset_version=entry.dataset_version,
            provider_used=entry.provider_used,
            warning_messages=entry.warning_messages,
            lineage_metadata=entry.lineage_metadata,
        )


def _compute_return_pct(previous_close: float | None, latest_close: float | None) -> float | None:
    if previous_close in (None, 0) or latest_close is None:
        return None
    return (latest_close / previous_close - 1.0) * 100.0


def _infer_trend_state(
    benchmark_return_1d: float | None,
    benchmark_return_20d: float | None,
) -> str:
    if benchmark_return_20d is None:
        return "unknown"
    if benchmark_return_20d >= 5.0:
        return "up"
    if benchmark_return_20d <= -5.0:
        return "down"
    if benchmark_return_1d is None:
        return "flat"
    if benchmark_return_1d > 0.8:
        return "up"
    if benchmark_return_1d < -0.8:
        return "down"
    return "flat"


def _compute_benchmark_penalty(
    benchmark_return_1d: float | None,
    benchmark_return_20d: float | None,
    benchmark_trend_state: str,
) -> float:
    score = 0.0
    if benchmark_return_1d is not None and benchmark_return_1d < 0:
        score += min(abs(benchmark_return_1d) * 10.0, 35.0)
    if benchmark_return_20d is not None and benchmark_return_20d < 0:
        score += min(abs(benchmark_return_20d) * 1.5, 45.0)
    if benchmark_trend_state == "down":
        score += 20.0
    elif benchmark_trend_state == "flat":
        score += 8.0
    return min(score, 100.0)
