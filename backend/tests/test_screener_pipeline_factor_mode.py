from contextlib import contextmanager
from datetime import date, timedelta
from typing import Iterator, Optional

from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.feature_service.screener_factor_service import ScreenerFactorService
from app.services.screener_service.cross_section_factor_service import CrossSectionFactorService
from app.services.screener_service.pipeline import ScreenerPipeline


class FactorModeMarketDataService:
    def __init__(self) -> None:
        self.session_scope_entered = 0

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        self.session_scope_entered += 1
        yield

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
        provider_names: Optional[tuple[str, ...]] = None,
    ) -> DailyBarResponse:
        if symbol == "600519.SH":
            bars = _build_bars(symbol=symbol, length=160, close_start=100.0, close_step=0.7, amount=180_000_000.0)
        elif symbol == "000001.SZ":
            bars = _build_bars(symbol=symbol, length=160, close_start=12.0, close_step=0.08, amount=60_000_000.0)
        else:
            bars = _build_bars(symbol=symbol, length=160, close_start=180.0, close_step=-0.15, amount=25_000_000.0)
        return DailyBarResponse(symbol=symbol, count=len(bars), bars=bars, quality_status="ok")

    def get_stock_financial_summary(
        self,
        symbol: str,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
    ) -> FinancialSummary:
        return FinancialSummary(
            symbol=symbol,
            name="stub",
            revenue=100.0,
            revenue_yoy=15.0,
            net_profit=20.0,
            net_profit_yoy=18.0,
            roe=16.0,
            debt_ratio=35.0,
            eps=2.0,
            source="stub",
            quality_status="ok",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(
            symbol=symbol,
            count=0,
            items=[],
            quality_status="ok",
            cleaning_warnings=[],
        )


class FactorModeTechnicalAnalysisService:
    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TechnicalSnapshot:
        return self.build_snapshot_from_bars(symbol, [])

    def build_snapshot_from_bars(self, symbol: str, bars: list[DailyBar]) -> TechnicalSnapshot:
        latest_close = bars[-1].close if bars else 0.0
        if symbol == "600519.SH":
            trend_state = "up"
            trend_score = 82
            volatility_state = "normal"
        elif symbol == "000001.SZ":
            trend_state = "neutral"
            trend_score = 60
            volatility_state = "normal"
        else:
            trend_state = "down"
            trend_score = 38
            volatility_state = "high"
        return TechnicalSnapshot(
            symbol=symbol,
            as_of_date=(bars[-1].trade_date if bars else date(2026, 4, 16)),
            latest_close=latest_close,
            latest_volume=bars[-1].volume if bars else None,
            moving_averages=MovingAverageSnapshot(),
            ema=EmaSnapshot(),
            macd=MacdSnapshot(),
            bollinger=BollingerSnapshot(),
            volume_metrics=VolumeMetricsSnapshot(),
            trend_state=trend_state,
            trend_score=trend_score,
            volatility_state=volatility_state,
            support_level=bars[-20].low if len(bars) >= 20 else None,
            resistance_level=bars[-20].high if len(bars) >= 20 else None,
        )


def test_run_screener_uses_new_screener_factor_pipeline() -> None:
    pipeline = ScreenerPipeline(
        market_data_service=FactorModeMarketDataService(),
        technical_analysis_service=FactorModeTechnicalAnalysisService(),
        screener_factor_service=ScreenerFactorService(),
        cross_section_factor_service=CrossSectionFactorService(),
        factor_snapshot_service=None,
    )

    response = pipeline.run_screener(
        scan_items=[
            UniverseItem(symbol="600519.SH", code="600519", exchange="SH", name="A", source="stub"),
            UniverseItem(symbol="000001.SZ", code="000001", exchange="SZ", name="B", source="stub"),
            UniverseItem(symbol="300750.SZ", code="300750", exchange="SZ", name="C", source="stub"),
        ],
    )

    assert response.total_symbols == 3
    assert response.scanned_symbols == 3
    assert response.buy_candidates
    assert response.buy_candidates[0].symbol == "600519.SH"
    assert response.buy_candidates[0].top_positive_factors
    assert response.avoid_candidates
    assert any(candidate.symbol == "300750.SZ" for candidate in response.avoid_candidates)


def _build_bars(
    *,
    symbol: str,
    length: int,
    close_start: float,
    close_step: float,
    amount: float,
    start_date: date = date(2025, 9, 1),
) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for index in range(length):
        close = max(close_start + close_step * index, 1.0)
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start_date + timedelta(days=index),
                open=close * 0.997,
                high=close * 1.012,
                low=close * 0.988,
                close=close,
                volume=amount / close,
                amount=amount,
                source="stub",
            ),
        )
    return bars
