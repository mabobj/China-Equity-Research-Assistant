from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_context_service
from app.core.config import get_settings
from app.schemas.market_data import DailyBar, DailyBarResponse
from app.main import app
from app.schemas.market_context import (
    BenchmarkCatalogResponse,
    BenchmarkDefinition,
    MarketBreadthSnapshot,
    RiskProxySnapshot,
    StockClassificationSnapshot,
)


class StubMarketContextService:
    def get_benchmark_catalog(self, *, as_of_date=None) -> BenchmarkCatalogResponse:
        return BenchmarkCatalogResponse(
            as_of_date=date(2026, 4, 9),
            count=1,
            items=[
                BenchmarkDefinition(
                    benchmark_id="csi300",
                    symbol="000300.SH",
                    name="沪深300",
                    exchange="SH",
                    category="large_cap",
                    is_primary=True,
                )
            ],
        )

    def get_market_breadth(
        self,
        *,
        as_of_date=None,
        max_symbols=None,
        force_refresh=False,
    ) -> MarketBreadthSnapshot:
        return MarketBreadthSnapshot(
            as_of_date=date(2026, 4, 9),
            universe_size=100,
            symbols_considered=80,
            symbols_skipped=20,
            coverage_ratio=0.8,
            advance_count=40,
            decline_count=30,
            flat_count=10,
            advance_ratio=0.5,
            decline_ratio=0.375,
            above_ma20_count=45,
            above_ma20_ratio=0.5625,
            above_ma60_count=38,
            above_ma60_ratio=0.475,
            new_20d_high_count=6,
            new_20d_low_count=3,
            mean_return_1d=0.9,
            median_return_1d=0.6,
            breadth_score=61.2,
            quality_status="ok",
            warning_messages=[],
            source_mode="local_snapshot",
            freshness_mode="computed",
        )

    def get_risk_proxy(
        self,
        *,
        as_of_date=None,
        max_symbols=None,
        force_refresh=False,
    ) -> RiskProxySnapshot:
        return RiskProxySnapshot(
            as_of_date=date(2026, 4, 9),
            universe_size=100,
            symbols_considered=80,
            breadth_score=61.2,
            cross_sectional_volatility_1d=1.4,
            median_return_1d=0.6,
            primary_benchmark_symbol="000300.SH",
            primary_benchmark_name="沪深300",
            benchmark_close=3888.0,
            benchmark_return_1d=0.8,
            benchmark_return_20d=5.6,
            benchmark_trend_state="up",
            risk_score=34.5,
            risk_regime="neutral",
            quality_status="ok",
            warning_messages=[],
            source_mode="breadth_plus_benchmark",
            freshness_mode="computed",
        )

    def get_benchmark_daily_bars(
        self,
        benchmark_symbol: str,
        *,
        as_of_date=None,
        lookback_days=120,
        force_refresh=False,
    ) -> DailyBarResponse:
        return DailyBarResponse(
            symbol=benchmark_symbol,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 4, 9),
            count=2,
            bars=[
                DailyBar(
                    symbol=benchmark_symbol,
                    trade_date=date(2026, 4, 8),
                    open=3800.0,
                    high=3820.0,
                    low=3790.0,
                    close=3805.0,
                    volume=1000.0,
                    amount=10000.0,
                    source="akshare",
                ),
                DailyBar(
                    symbol=benchmark_symbol,
                    trade_date=date(2026, 4, 9),
                    open=3820.0,
                    high=3890.0,
                    low=3810.0,
                    close=3888.0,
                    volume=1200.0,
                    amount=12000.0,
                    source="akshare",
                ),
            ],
            quality_status="ok",
        )

    def get_stock_classification(
        self,
        symbol: str,
        *,
        as_of_date=None,
        force_refresh=False,
    ) -> StockClassificationSnapshot:
        return StockClassificationSnapshot(
            symbol=symbol,
            name="平安银行",
            exchange="SZ",
            board="main_board",
            industry="银行",
            as_of_date=date(2026, 4, 9),
            quality_status="ok",
            warning_messages=[],
            primary_benchmark_symbol="000300.SH",
            primary_benchmark_name="沪深300",
        )


def test_market_context_routes_return_typed_payloads() -> None:
    app.dependency_overrides[get_market_context_service] = lambda: StubMarketContextService()
    client = TestClient(app)
    api_prefix = get_settings().api_prefix
    try:
        benchmarks_response = client.get(f"{api_prefix}/market/benchmarks")
        assert benchmarks_response.status_code == 200
        assert benchmarks_response.json()["count"] == 1

        breadth_response = client.get(f"{api_prefix}/market/breadth")
        assert breadth_response.status_code == 200
        assert breadth_response.json()["quality_status"] == "ok"

        risk_response = client.get(f"{api_prefix}/market/risk-proxies")
        assert risk_response.status_code == 200
        assert risk_response.json()["risk_regime"] == "neutral"
        assert risk_response.json()["primary_benchmark_symbol"] == "000300.SH"

        benchmark_bar_response = client.get(
            f"{api_prefix}/market/benchmarks/000300.SH/daily-bars",
        )
        assert benchmark_bar_response.status_code == 200
        assert benchmark_bar_response.json()["count"] == 2

        classification_response = client.get(
            f"{api_prefix}/stocks/000001.SZ/classification",
        )
        assert classification_response.status_code == 200
        assert classification_response.json()["board"] == "main_board"
    finally:
        app.dependency_overrides.clear()
