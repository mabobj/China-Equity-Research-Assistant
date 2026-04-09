"""日线价格口径与公司行为元数据测试。"""

from datetime import date
from pathlib import Path

from app.db.market_data_store import LocalMarketDataStore
from app.schemas.market_data import DailyBar
from app.services.data_service.market_data_service import MarketDataService


class RawDailyProvider:
    name = "akshare"
    capabilities = ("daily_bars",)

    def is_available(self) -> bool:
        return True

    def get_daily_bars(self, symbol: str, start_date=None, end_date=None) -> list[DailyBar]:
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=10.0,
                amount=1000.0,
                adjustment_mode="raw",
                corporate_action_flags=[],
                source=self.name,
            )
        ]


def test_daily_bar_roundtrip_preserves_adjustment_and_action_metadata(tmp_path: Path) -> None:
    store = LocalMarketDataStore(tmp_path / "market.duckdb")
    store.upsert_daily_bars(
        [
            DailyBar(
                symbol="600519.SH",
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                adjustment_mode="raw",
                trading_status="normal",
                corporate_action_flags=["dividend"],
                source="akshare",
            )
        ]
    )

    rows = store.get_daily_bars("600519.SH")

    assert len(rows) == 1
    assert rows[0].adjustment_mode == "raw"
    assert rows[0].trading_status == "normal"
    assert rows[0].corporate_action_flags == ["dividend"]


def test_market_data_service_exposes_adjustment_metadata_in_response() -> None:
    service = MarketDataService(providers=[RawDailyProvider()])

    response = service.get_daily_bars(
        "600519.SH",
        start_date="2024-01-01",
        end_date="2024-01-02",
    )

    assert response.adjustment_mode == "raw"
    assert response.corporate_action_mode == "unmodeled"
    assert "corporate_actions_not_modeled_yet" in response.corporate_action_warnings
