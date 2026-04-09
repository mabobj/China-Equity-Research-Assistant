from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_context_service
from app.core.config import get_settings
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
            risk_score=34.5,
            risk_regime="neutral",
            quality_status="ok",
            warning_messages=[],
            source_mode="derived_from_breadth",
            freshness_mode="computed",
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

        classification_response = client.get(
            f"{api_prefix}/stocks/000001.SZ/classification",
        )
        assert classification_response.status_code == 200
        assert classification_response.json()["board"] == "main_board"
    finally:
        app.dependency_overrides.clear()
