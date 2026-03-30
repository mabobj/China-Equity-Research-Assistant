"""选股池加载测试。"""

from __future__ import annotations

from app.schemas.market_data import UniverseItem, UniverseResponse
from app.services.screener_service.universe import load_scan_universe


class StubMarketDataService:
    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=4,
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    name="贵州茅台",
                    code="600519",
                    exchange="SH",
                    source="test",
                ),
                UniverseItem(
                    symbol="000001.SZ",
                    name="平安银行",
                    code="000001",
                    exchange="SZ",
                    source="test",
                ),
                UniverseItem(
                    symbol="600000.SH",
                    name="浦发银行",
                    code="600000",
                    exchange="SH",
                    source="test",
                ),
                UniverseItem(
                    symbol="300750.SZ",
                    name="宁德时代",
                    code="300750",
                    exchange="SZ",
                    source="test",
                ),
            ],
        )


def test_load_scan_universe_applies_stable_symbol_sorting() -> None:
    total, items = load_scan_universe(
        market_data_service=StubMarketDataService(),
        max_symbols=3,
    )

    assert total == 4
    assert [item.symbol for item in items] == [
        "000001.SZ",
        "300750.SZ",
        "600000.SH",
    ]
