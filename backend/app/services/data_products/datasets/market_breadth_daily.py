"""市场广度日级数据产品。"""

from __future__ import annotations

from datetime import date
from statistics import mean, median

from app.db.market_data_store import LocalMarketDataStore
from app.schemas.market_context import MarketBreadthSnapshot
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import MARKET_BREADTH_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository
from app.services.data_service.market_data_service import MarketDataService


class MarketBreadthDailyDataset:
    """按日计算并缓存市场广度快照。"""

    def __init__(
        self,
        *,
        repository: DataProductRepository,
        market_data_service: MarketDataService,
        local_store: LocalMarketDataStore | None,
    ) -> None:
        self._repository = repository
        self._market_data_service = market_data_service
        self._local_store = local_store

    def get(
        self,
        *,
        as_of_date=None,
        max_symbols: int | None = None,
        force_refresh: bool = False,
    ) -> DataProductResult[MarketBreadthSnapshot]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        params_hash = self._repository.build_params_hash({"max_symbols": max_symbols})
        if not force_refresh:
            cached = self._repository.load(
                dataset=MARKET_BREADTH_DAILY,
                symbol="__market__",
                as_of_date=resolved_as_of_date,
                params_hash=params_hash,
            )
            if cached is not None:
                payload = MarketBreadthSnapshot.model_validate(cached.payload)
                return DataProductResult(
                    dataset=MARKET_BREADTH_DAILY,
                    symbol="__market__",
                    as_of_date=cached.as_of_date,
                    payload=payload,
                    freshness_mode="cache_hit",
                    source_mode="snapshot",
                    updated_at=cached.updated_at,
                )

        payload = self._build_snapshot(
            as_of_date=resolved_as_of_date,
            max_symbols=max_symbols,
        )
        entry = self._repository.create_entry(
            dataset=MARKET_BREADTH_DAILY,
            symbol="__market__",
            as_of_date=resolved_as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode=payload.source_mode,
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=MARKET_BREADTH_DAILY,
            symbol="__market__",
            as_of_date=resolved_as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode=payload.source_mode,
            updated_at=entry.updated_at,
        )

    def _build_snapshot(
        self,
        *,
        as_of_date: date,
        max_symbols: int | None,
    ) -> MarketBreadthSnapshot:
        universe_items = self._market_data_service.get_stock_universe().items
        if max_symbols is not None:
            universe_items = universe_items[: max(0, max_symbols)]
        universe_size = len(universe_items)
        symbols = [item.symbol for item in universe_items]

        if self._local_store is not None:
            bars_by_symbol = self._local_store.get_daily_bars_for_symbols(
                symbols,
                start_date=as_of_date.fromordinal(as_of_date.toordinal() - 90),
                end_date=as_of_date,
                adjustment_mode="raw",
            )
            source_mode = "local_snapshot"
        else:
            bars_by_symbol = {}
            source_mode = "service_fallback"
            for symbol in symbols:
                response = self._market_data_service.get_daily_bars(
                    symbol=symbol,
                    end_date=as_of_date.isoformat(),
                    adjustment_mode="raw",
                    allow_remote_sync=False,
                )
                bars_by_symbol[symbol] = response.bars

        advance_count = 0
        decline_count = 0
        flat_count = 0
        above_ma20_count = 0
        above_ma60_count = 0
        new_20d_high_count = 0
        new_20d_low_count = 0
        return_1d_values: list[float] = []
        symbols_considered = 0
        warning_messages: list[str] = []

        for symbol in symbols:
            bars = [bar for bar in bars_by_symbol.get(symbol, []) if bar.trade_date <= as_of_date]
            if not bars:
                continue
            bars.sort(key=lambda item: item.trade_date)
            if bars[-1].trade_date != as_of_date or bars[-1].close is None:
                continue
            if len(bars) < 2 or bars[-2].close is None:
                continue

            latest_close = float(bars[-1].close)
            previous_close = float(bars[-2].close)
            if previous_close <= 0:
                continue

            symbols_considered += 1
            return_1d = (latest_close / previous_close - 1.0) * 100.0
            return_1d_values.append(return_1d)

            if return_1d > 0:
                advance_count += 1
            elif return_1d < 0:
                decline_count += 1
            else:
                flat_count += 1

            recent_20 = [
                float(bar.close)
                for bar in bars[-20:]
                if bar.close is not None
            ]
            recent_60 = [
                float(bar.close)
                for bar in bars[-60:]
                if bar.close is not None
            ]
            if len(recent_20) >= 20:
                if latest_close > mean(recent_20):
                    above_ma20_count += 1
                if latest_close >= max(recent_20):
                    new_20d_high_count += 1
                if latest_close <= min(recent_20):
                    new_20d_low_count += 1
            if len(recent_60) >= 60 and latest_close > mean(recent_60):
                above_ma60_count += 1

        symbols_skipped = max(universe_size - symbols_considered, 0)
        coverage_ratio = (
            symbols_considered / universe_size if universe_size > 0 else 0.0
        )
        if coverage_ratio < 0.2:
            quality_status = "degraded"
            warning_messages.append("breadth_coverage_too_low")
        elif coverage_ratio < 0.5:
            quality_status = "warning"
            warning_messages.append("breadth_coverage_partial")
        else:
            quality_status = "ok"

        denominator = symbols_considered if symbols_considered > 0 else 1
        advance_ratio = advance_count / denominator
        decline_ratio = decline_count / denominator
        above_ma20_ratio = above_ma20_count / denominator
        above_ma60_ratio = above_ma60_count / denominator
        high_low_denominator = new_20d_high_count + new_20d_low_count
        if high_low_denominator > 0:
            high_low_balance = new_20d_high_count / high_low_denominator
        else:
            high_low_balance = 0.5
            warning_messages.append("new_high_low_balance_neutralized")

        breadth_score = max(
            0.0,
            min(
                100.0,
                (
                    advance_ratio * 0.35
                    + above_ma20_ratio * 0.25
                    + above_ma60_ratio * 0.25
                    + high_low_balance * 0.15
                )
                * 100.0,
            ),
        )

        return MarketBreadthSnapshot(
            as_of_date=as_of_date,
            universe_size=universe_size,
            symbols_considered=symbols_considered,
            symbols_skipped=symbols_skipped,
            coverage_ratio=coverage_ratio,
            advance_count=advance_count,
            decline_count=decline_count,
            flat_count=flat_count,
            advance_ratio=advance_ratio,
            decline_ratio=decline_ratio,
            above_ma20_count=above_ma20_count,
            above_ma20_ratio=above_ma20_ratio,
            above_ma60_count=above_ma60_count,
            above_ma60_ratio=above_ma60_ratio,
            new_20d_high_count=new_20d_high_count,
            new_20d_low_count=new_20d_low_count,
            mean_return_1d=mean(return_1d_values) if return_1d_values else None,
            median_return_1d=median(return_1d_values) if return_1d_values else None,
            breadth_score=breadth_score,
            quality_status=quality_status,
            warning_messages=list(dict.fromkeys(warning_messages)),
            source_mode=source_mode,
            freshness_mode="computed",
        )
