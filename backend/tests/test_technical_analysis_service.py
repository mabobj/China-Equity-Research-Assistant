"""技术分析服务测试。"""

from datetime import date, timedelta
from typing import Optional

from app.schemas.market_data import DailyBar, DailyBarResponse
from app.services.feature_service.technical_analysis_service import (
    TechnicalAnalysisService,
)


class FakeMarketDataService:
    """用于技术分析服务测试的假数据服务。"""

    def __init__(self) -> None:
        self.symbol: Optional[str] = None
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        return DailyBarResponse(
            symbol=symbol,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 9),
            count=40,
            bars=_build_bars(symbol=symbol, length=40),
        )


def test_get_technical_snapshot_returns_structured_snapshot() -> None:
    """技术分析服务应返回结构化快照。"""
    market_data_service = FakeMarketDataService()
    service = TechnicalAnalysisService(market_data_service=market_data_service)

    snapshot = service.get_technical_snapshot(
        symbol="sh600519",
        start_date="2024-01-01",
        end_date="2024-02-09",
    )

    assert market_data_service.symbol == "600519.SH"
    assert snapshot.symbol == "600519.SH"
    assert snapshot.as_of_date == date(2024, 2, 9)
    assert snapshot.latest_close == 40.0
    assert snapshot.moving_averages.ma5 is not None
    assert snapshot.macd.macd is not None
    assert snapshot.trend_state in {"up", "neutral", "down"}
    assert 0 <= snapshot.trend_score <= 100
    assert snapshot.volatility_state in {"low", "normal", "high"}


def _build_bars(symbol: str, length: int) -> list[DailyBar]:
    """构造用于技术分析测试的日线数据。"""
    bars = []
    start = date(2024, 1, 1)
    for index in range(1, length + 1):
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start + timedelta(days=index - 1),
                open=float(index) - 0.5,
                high=float(index) + 1.0,
                low=float(index) - 1.0,
                close=float(index),
                volume=float(index * 1000),
                amount=float(index * 10000),
                source="fake",
            )
        )

    return bars
