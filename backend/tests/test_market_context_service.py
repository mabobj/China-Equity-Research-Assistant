from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.db.market_data_store import LocalMarketDataStore
from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.services.data_products.datasets.benchmark_catalog_daily import (
    BenchmarkCatalogDailyDataset,
)
from app.services.data_products.datasets.industry_classification_daily import (
    IndustryClassificationDailyDataset,
)
from app.services.data_products.datasets.market_breadth_daily import (
    MarketBreadthDailyDataset,
)
from app.services.data_products.datasets.risk_proxy_daily import RiskProxyDailyDataset
from app.services.data_products.repository import DataProductRepository
from app.services.data_service.market_context_service import MarketContextService


class FakeMarketDataService:
    def __init__(
        self,
        *,
        universe_items: list[UniverseItem],
        profiles: dict[str, StockProfile],
    ) -> None:
        self._universe_items = universe_items
        self._profiles = profiles

    def get_stock_universe(self):
        return type("UniverseResponseStub", (), {"items": self._universe_items})()

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return self._profiles[symbol]


def _build_bar_series(
    *,
    symbol: str,
    source: str,
    as_of_date: date,
    closes: list[float],
) -> list[DailyBar]:
    start_date = as_of_date - timedelta(days=len(closes) - 1)
    bars: list[DailyBar] = []
    for index, close_value in enumerate(closes):
        trade_date = start_date + timedelta(days=index)
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=trade_date,
                open=close_value,
                high=close_value,
                low=close_value,
                close=close_value,
                volume=1000.0 + index,
                amount=10000.0 + index,
                adjustment_mode="raw",
                source=source,
            )
        )
    return bars


def test_market_context_service_builds_classification_breadth_and_risk(tmp_path: Path) -> None:
    as_of_date = date(2026, 4, 9)
    store = LocalMarketDataStore(tmp_path / "market.duckdb")
    repository = DataProductRepository(tmp_path / "daily_products")

    universe_items = [
        UniverseItem(
            symbol="300001.SZ",
            code="300001",
            exchange="SZ",
            name="示例创业板",
            status="active",
            source="akshare",
        ),
        UniverseItem(
            symbol="600001.SH",
            code="600001",
            exchange="SH",
            name="示例主板",
            status="active",
            source="akshare",
        ),
        UniverseItem(
            symbol="688001.SH",
            code="688001",
            exchange="SH",
            name="示例科创板",
            status="active",
            source="akshare",
        ),
    ]
    store.replace_stock_universe(universe_items)
    store.upsert_daily_bars(
        _build_bar_series(
            symbol="300001.SZ",
            source="akshare",
            as_of_date=as_of_date,
            closes=[10.0 + idx * 0.2 for idx in range(60)],
        )
        + _build_bar_series(
            symbol="600001.SH",
            source="akshare",
            as_of_date=as_of_date,
            closes=[20.0 - idx * 0.1 for idx in range(60)],
        )
        + _build_bar_series(
            symbol="688001.SH",
            source="akshare",
            as_of_date=as_of_date,
            closes=[30.0 for _ in range(60)],
        )
    )

    profiles = {
        "300001.SZ": StockProfile(
            symbol="300001.SZ",
            code="300001",
            exchange="SZ",
            name="示例创业板",
            industry="电力设备",
            source="akshare",
        ),
        "600001.SH": StockProfile(
            symbol="600001.SH",
            code="600001",
            exchange="SH",
            name="示例主板",
            industry="银行",
            source="akshare",
        ),
        "688001.SH": StockProfile(
            symbol="688001.SH",
            code="688001",
            exchange="SH",
            name="示例科创板",
            industry=None,
            source="akshare",
        ),
    }
    fake_market_data_service = FakeMarketDataService(
        universe_items=universe_items,
        profiles=profiles,
    )

    service = MarketContextService(
        benchmark_catalog_daily=BenchmarkCatalogDailyDataset(),
        industry_classification_daily=IndustryClassificationDailyDataset(
            repository=repository,
            market_data_service=fake_market_data_service,
        ),
        market_breadth_daily=MarketBreadthDailyDataset(
            repository=repository,
            market_data_service=fake_market_data_service,
            local_store=store,
        ),
        risk_proxy_daily=RiskProxyDailyDataset(
            repository=repository,
            market_breadth_daily=MarketBreadthDailyDataset(
                repository=repository,
                market_data_service=fake_market_data_service,
                local_store=store,
            ),
        ),
    )

    classification = service.get_stock_classification(
        "300001.SZ",
        as_of_date=as_of_date,
    )
    assert classification.board == "chinext"
    assert classification.primary_benchmark_symbol == "399006.SZ"
    assert classification.quality_status == "ok"

    classification_warning = service.get_stock_classification(
        "688001.SH",
        as_of_date=as_of_date,
    )
    assert classification_warning.board == "star_market"
    assert classification_warning.quality_status == "warning"
    assert "industry_missing_use_board_only" in classification_warning.warning_messages

    benchmark_catalog = service.get_benchmark_catalog(as_of_date=as_of_date)
    assert benchmark_catalog.count >= 5
    assert any(item.is_primary for item in benchmark_catalog.items)

    breadth = service.get_market_breadth(as_of_date=as_of_date)
    assert breadth.universe_size == 3
    assert breadth.symbols_considered == 3
    assert breadth.advance_count == 1
    assert breadth.decline_count == 1
    assert breadth.flat_count == 1
    assert breadth.quality_status == "ok"

    risk = service.get_risk_proxy(as_of_date=as_of_date)
    assert risk.universe_size == 3
    assert risk.quality_status == "ok"
    assert risk.risk_regime in {"risk_on", "neutral", "risk_off"}
