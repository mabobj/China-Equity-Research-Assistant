from __future__ import annotations

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


class _PersistingMarketDataService:
    @contextmanager
    def session_scope(self) -> Iterator[None]:
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
            bars = _build_bars(symbol=symbol, close_start=100.0, close_step=0.7, amount=180_000_000.0)
        else:
            bars = _build_bars(symbol=symbol, close_start=12.0, close_step=0.08, amount=60_000_000.0)
        return DailyBarResponse(
            symbol=symbol,
            count=len(bars),
            bars=bars,
            quality_status="ok",
        )

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


class _PersistingTechnicalAnalysisService:
    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TechnicalSnapshot:
        return self.build_snapshot_from_bars(symbol, [])

    def build_snapshot_from_bars(self, symbol: str, bars: list[DailyBar]) -> TechnicalSnapshot:
        latest_close = bars[-1].close if bars else 0.0
        trend_score = 80 if symbol == "600519.SH" else 58
        trend_state = "up" if symbol == "600519.SH" else "neutral"
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
            volatility_state="normal",
            support_level=bars[-20].low if len(bars) >= 20 else None,
            resistance_level=bars[-20].high if len(bars) >= 20 else None,
        )


class _RecordingScreenerFactorSnapshotDailyDataset:
    def __init__(self) -> None:
        self.saved: list[dict[str, object]] = []

    def save(self, symbol: str, *, params, payload):
        self.saved.append({"symbol": symbol, "params": params, "payload": payload})
        return type(
            "_SavedResult",
            (),
            {
                "lineage_metadata": payload.lineage_metadata,
            },
        )()


class _RecordingLineageService:
    def __init__(self) -> None:
        self.registered = []

    def register_data_product(self, result) -> None:
        self.registered.append(result)


def test_pipeline_persists_screener_factor_snapshots_and_registers_lineage() -> None:
    snapshot_dataset = _RecordingScreenerFactorSnapshotDailyDataset()
    lineage_service = _RecordingLineageService()
    pipeline = ScreenerPipeline(
        market_data_service=_PersistingMarketDataService(),
        technical_analysis_service=_PersistingTechnicalAnalysisService(),
        screener_factor_service=ScreenerFactorService(),
        cross_section_factor_service=CrossSectionFactorService(),
        factor_snapshot_service=None,
        screener_factor_snapshot_daily=snapshot_dataset,
        lineage_service=lineage_service,
    )

    response = pipeline.run_screener(
        max_symbols=2,
        top_n=1,
        scan_items=[
            UniverseItem(symbol="600519.SH", code="600519", exchange="SH", name="A", source="stub"),
            UniverseItem(symbol="000001.SZ", code="000001", exchange="SZ", name="B", source="stub"),
        ],
        run_context={
            "workflow_name": "screener_run",
            "batch_size": 2,
            "cursor_start_symbol": "000001.SZ",
            "cursor_start_index": 0,
            "reset_trade_date": "2026-04-16",
        },
    )

    assert response.scanned_symbols == 2
    assert len(snapshot_dataset.saved) == 2
    assert len(lineage_service.registered) == 2
    first_saved = snapshot_dataset.saved[0]
    assert first_saved["params"].workflow_name == "screener_run"
    assert first_saved["params"].max_symbols == 2
    assert first_saved["params"].top_n == 1
    assert first_saved["payload"].composite_score is not None
    assert first_saved["payload"].selection_decision is not None


def _build_bars(
    *,
    symbol: str,
    close_start: float,
    close_step: float,
    amount: float,
    length: int = 160,
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
                source="mootdx",
            ),
        )
    return bars
