"""基础风险代理日级数据产品。"""

from __future__ import annotations

from statistics import pstdev

from app.schemas.market_context import RiskProxySnapshot
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import RISK_PROXY_DAILY
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
        market_breadth_daily: MarketBreadthDailyDataset,
    ) -> None:
        self._repository = repository
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
                )

        breadth_result = self._market_breadth_daily.get(
            as_of_date=resolved_as_of_date,
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        )
        breadth = breadth_result.payload
        cross_sectional_volatility = None
        warning_messages = list(breadth.warning_messages)

        # 当前第一版没有逐股 1 日收益分布持久化，这里仅用 breadth 汇总进行保守风险代理。
        if breadth.mean_return_1d is not None and breadth.median_return_1d is not None:
            cross_sectional_volatility = abs(
                breadth.mean_return_1d - breadth.median_return_1d,
            )
        else:
            warning_messages.append("cross_sectional_volatility_proxy_limited")

        breadth_penalty = 100.0 - breadth.breadth_score
        volatility_penalty = 0.0
        if cross_sectional_volatility is not None:
            volatility_penalty = min(cross_sectional_volatility * 18.0, 100.0)
        risk_score = max(
            0.0,
            min(
                100.0,
                breadth_penalty * 0.7 + volatility_penalty * 0.3,
            ),
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
            risk_score=risk_score,
            risk_regime=risk_regime,
            quality_status=quality_status,
            warning_messages=list(dict.fromkeys(warning_messages)),
            source_mode="derived_from_breadth",
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
        )
