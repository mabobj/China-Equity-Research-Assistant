"""Tests for intraday service."""

from __future__ import annotations

from datetime import datetime

from app.schemas.market_data import IntradayBar, IntradayBarResponse
from app.services.data_service.intraday_service import IntradayService


class StubMarketDataService:
    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        limit: int | None = None,
    ) -> IntradayBarResponse:
        return IntradayBarResponse(
            symbol="600519.SH",
            frequency=frequency,
            count=3,
            bars=[
                IntradayBar(
                    symbol="600519.SH",
                    trade_datetime=datetime(2024, 1, 2, 9, 31, 0),
                    frequency=frequency,
                    open=100.0,
                    high=100.8,
                    low=99.9,
                    close=100.5,
                    volume=100.0,
                    amount=10000.0,
                    source="stub",
                ),
                IntradayBar(
                    symbol="600519.SH",
                    trade_datetime=datetime(2024, 1, 2, 9, 32, 0),
                    frequency=frequency,
                    open=100.5,
                    high=101.0,
                    low=100.2,
                    close=100.9,
                    volume=120.0,
                    amount=12000.0,
                    source="stub",
                ),
                IntradayBar(
                    symbol="600519.SH",
                    trade_datetime=datetime(2024, 1, 2, 9, 33, 0),
                    frequency=frequency,
                    open=100.9,
                    high=101.2,
                    low=100.6,
                    close=101.1,
                    volume=150.0,
                    amount=15000.0,
                    source="stub",
                ),
            ],
        )


def test_intraday_service_builds_snapshot() -> None:
    service = IntradayService(market_data_service=StubMarketDataService())

    snapshot = service.get_intraday_snapshot("600519.SH", frequency="1m", limit=60)

    assert snapshot.symbol == "600519.SH"
    assert snapshot.frequency == "1m"
    assert snapshot.latest_price == 101.1
    assert snapshot.latest_datetime == datetime(2024, 1, 2, 9, 33, 0)
    assert snapshot.session_open == 100.0
    assert snapshot.session_high == 101.2
    assert snapshot.session_low == 99.9
    assert snapshot.volume_sum == 370.0
