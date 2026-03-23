"""选股器 pipeline 测试。"""

from datetime import date, timedelta

from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem, UniverseResponse
from app.schemas.screener import ScreenerRunResponse
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.screener_service.pipeline import ScreenerPipeline


class FakeMarketDataService:
    """用于选股器测试的假市场数据服务。"""

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=4,
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    code="600519",
                    exchange="SH",
                    name="贵州茅台",
                    source="fake",
                ),
                UniverseItem(
                    symbol="000001.SZ",
                    code="000001",
                    exchange="SZ",
                    name="平安银行",
                    source="fake",
                ),
                UniverseItem(
                    symbol="300750.SZ",
                    code="300750",
                    exchange="SZ",
                    name="*ST测试",
                    source="fake",
                ),
                UniverseItem(
                    symbol="688001.SH",
                    code="688001",
                    exchange="SH",
                    name="华兴股份",
                    source="fake",
                ),
            ],
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> DailyBarResponse:
        if symbol == "688001.SH":
            return DailyBarResponse(
                symbol=symbol,
                count=20,
                bars=_build_bars(symbol=symbol, length=20, close_start=10.0),
            )

        if symbol == "000001.SZ":
            return DailyBarResponse(
                symbol=symbol,
                count=40,
                bars=_build_bars(
                    symbol=symbol,
                    length=40,
                    close_start=8.0,
                    amount=8_000_000.0,
                ),
            )

        return DailyBarResponse(
            symbol=symbol,
            count=40,
            bars=_build_bars(
                symbol=symbol,
                length=40,
                close_start=100.0,
                amount=60_000_000.0,
            ),
        )


class FakeTechnicalAnalysisService:
    """用于选股器测试的假技术分析服务。"""

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> TechnicalSnapshot:
        if symbol == "600519.SH":
            return _build_snapshot(
                symbol=symbol,
                trend_state="up",
                trend_score=80,
                latest_close=120.0,
                support_level=115.0,
                resistance_level=122.0,
                volume_ratio_to_ma20=1.15,
            )

        return _build_snapshot(
            symbol=symbol,
            trend_state="neutral",
            trend_score=58,
            latest_close=20.0,
            support_level=19.0,
            resistance_level=22.0,
            volume_ratio_to_ma20=0.95,
        )


def test_run_screener_returns_bucketed_candidates() -> None:
    """pipeline 应返回按分桶组织的结构化结果。"""
    pipeline = ScreenerPipeline(
        market_data_service=FakeMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
    )

    response = pipeline.run_screener()

    assert isinstance(response, ScreenerRunResponse)
    assert response.total_symbols == 4
    assert response.scanned_symbols == 3
    assert len(response.buy_candidates) == 1
    assert response.buy_candidates[0].symbol == "600519.SH"
    assert response.buy_candidates[0].rank == 1
    assert len(response.watch_candidates) == 0
    assert len(response.avoid_candidates) == 0


def _build_bars(
    symbol: str,
    length: int,
    close_start: float,
    amount: float = 50_000_000.0,
) -> list[DailyBar]:
    """构造测试用日线数据。"""
    start = date(2024, 1, 1)
    bars: list[DailyBar] = []
    for index in range(length):
        close_value = close_start + index * 0.5
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start + timedelta(days=index),
                open=close_value - 0.2,
                high=close_value + 0.5,
                low=close_value - 0.5,
                close=close_value,
                volume=500000.0 + index * 1000.0,
                amount=amount,
                source="fake",
            )
        )
    return bars


def _build_snapshot(
    symbol: str,
    trend_state: str,
    trend_score: int,
    latest_close: float,
    support_level: float,
    resistance_level: float,
    volume_ratio_to_ma20: float,
) -> TechnicalSnapshot:
    """构造测试用技术快照。"""
    return TechnicalSnapshot(
        symbol=symbol,
        as_of_date=date(2024, 3, 25),
        latest_close=latest_close,
        latest_volume=600000.0,
        moving_averages=MovingAverageSnapshot(
            ma5=latest_close - 1.0,
            ma10=latest_close - 1.5,
            ma20=latest_close - 2.0,
            ma60=latest_close - 4.0,
            ma120=latest_close - 6.0,
        ),
        ema=EmaSnapshot(
            ema12=latest_close - 1.2,
            ema26=latest_close - 2.1,
        ),
        macd=MacdSnapshot(
            macd=2.0,
            signal=1.4,
            histogram=0.6,
        ),
        rsi14=58.0,
        atr14=1.5,
        bollinger=BollingerSnapshot(
            middle=latest_close - 2.0,
            upper=latest_close + 3.0,
            lower=latest_close - 5.0,
        ),
        volume_metrics=VolumeMetricsSnapshot(
            volume_ma5=580000.0,
            volume_ma20=550000.0,
            volume_ratio_to_ma5=1.03,
            volume_ratio_to_ma20=volume_ratio_to_ma20,
        ),
        trend_state=trend_state,
        trend_score=trend_score,
        volatility_state="normal",
        support_level=support_level,
        resistance_level=resistance_level,
    )

