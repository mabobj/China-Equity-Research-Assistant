"""Tests for trigger snapshot service."""

from datetime import date, datetime

from app.schemas.intraday import IntradaySnapshot
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.data_service.exceptions import DataServiceError
from app.services.factor_service.trigger_snapshot_service import TriggerSnapshotService


class StubTechnicalAnalysisService:
    def get_technical_snapshot(self, symbol: str):
        return TechnicalSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 1, 2),
            latest_close=101.0,
            latest_volume=1000.0,
            moving_averages=MovingAverageSnapshot(),
            ema=EmaSnapshot(),
            macd=MacdSnapshot(),
            rsi14=60.0,
            atr14=2.0,
            bollinger=BollingerSnapshot(),
            volume_metrics=VolumeMetricsSnapshot(),
            trend_state="up",
            trend_score=78,
            volatility_state="normal",
            support_level=100.0,
            resistance_level=102.0,
        )


class StubIntradayService:
    def get_intraday_snapshot(self, symbol: str, frequency: str = "1m", limit: int = 60):
        return IntradaySnapshot(
            symbol="600519.SH",
            frequency=frequency,
            latest_price=101.3,
            latest_datetime=datetime(2024, 1, 2, 10, 0, 0),
            session_high=101.5,
            session_low=100.2,
            session_open=100.5,
            volume_sum=5000.0,
            intraday_return_pct=0.8,
            range_pct=1.2,
            source="stub",
        )


class BrokenIntradayService:
    def get_intraday_snapshot(self, symbol: str, frequency: str = "1m", limit: int = 60):
        raise DataServiceError("intraday unavailable")


def test_trigger_snapshot_service_returns_near_breakout() -> None:
    service = TriggerSnapshotService(
        technical_analysis_service=StubTechnicalAnalysisService(),
        intraday_service=StubIntradayService(),
    )

    snapshot = service.get_trigger_snapshot("600519.SH", frequency="1m", limit=60)

    assert snapshot.symbol == "600519.SH"
    assert snapshot.trigger_state == "near_breakout"
    assert snapshot.daily_support_level == 100.0
    assert snapshot.daily_resistance_level == 102.0
    assert snapshot.latest_intraday_price == 101.3


def test_trigger_snapshot_service_falls_back_when_intraday_unavailable() -> None:
    service = TriggerSnapshotService(
        technical_analysis_service=StubTechnicalAnalysisService(),
        intraday_service=BrokenIntradayService(),
    )

    snapshot = service.get_trigger_snapshot("600519.SH", frequency="1m", limit=60)

    assert snapshot.symbol == "600519.SH"
    assert snapshot.as_of_datetime == datetime(2024, 1, 2, 15, 0, 0)
    assert snapshot.latest_intraday_price == 101.0
    assert "缺少盘中数据" in snapshot.trigger_note
