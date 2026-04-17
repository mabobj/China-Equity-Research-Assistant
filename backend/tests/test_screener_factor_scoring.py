from datetime import date, timedelta

from app.schemas.market_data import DailyBar
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
from app.services.screener_service.scoring import (
    apply_score_to_screener_factor_snapshot,
    score_screener_factor_snapshot,
)


def test_score_screener_factor_snapshot_returns_ready_candidate_for_strong_setup() -> None:
    factor_service = ScreenerFactorService()
    snapshots = [
        factor_service.build_snapshot_from_bars(
            symbol="600519.SH",
            bars=_build_bars(
                symbol="600519.SH",
                length=160,
                close_start=100.0,
                close_step=0.7,
                amount=180_000_000.0,
            ),
            industry="Consumer",
            list_date=date(2001, 8, 27),
        ),
        factor_service.build_snapshot_from_bars(
            symbol="000001.SZ",
            bars=_build_bars(
                symbol="000001.SZ",
                length=160,
                close_start=12.0,
                close_step=0.08,
                amount=60_000_000.0,
            ),
            industry="Bank",
            list_date=date(1991, 4, 3),
        ),
        factor_service.build_snapshot_from_bars(
            symbol="300750.SZ",
            bars=_build_bars(
                symbol="300750.SZ",
                length=160,
                close_start=180.0,
                close_step=-0.15,
                amount=25_000_000.0,
            ),
            industry="Battery",
            list_date=date(2018, 6, 11),
        ),
    ]
    enriched = CrossSectionFactorService().enrich_snapshots(snapshots)
    snapshot = next(item for item in enriched if item.symbol == "600519.SH")

    technical_snapshot = TechnicalSnapshot(
        symbol="600519.SH",
        as_of_date=snapshot.as_of_date,
        latest_close=snapshot.raw_inputs.latest_close or 0.0,
        latest_volume=snapshot.raw_inputs.latest_volume,
        moving_averages=MovingAverageSnapshot(
            ma20=snapshot.process_metrics.ma_20,
            ma60=snapshot.process_metrics.ma_60,
            ma120=snapshot.process_metrics.ma_120,
        ),
        ema=EmaSnapshot(),
        macd=MacdSnapshot(),
        bollinger=BollingerSnapshot(),
        volume_metrics=VolumeMetricsSnapshot(
            volume_ma20=None,
            volume_ratio_to_ma20=None,
        ),
        trend_state="up",
        trend_score=80,
        volatility_state="normal",
        support_level=snapshot.process_metrics.support_level_20d,
        resistance_level=snapshot.process_metrics.resistance_level_20d,
    )

    result = score_screener_factor_snapshot(
        screener_factor_snapshot=snapshot,
        technical_snapshot=technical_snapshot,
    )

    assert result.list_type == "BUY_CANDIDATE"
    assert result.v2_list_type == "READY_TO_BUY"
    assert result.alpha_score >= 70
    assert result.trigger_score >= 68
    assert result.risk_score <= 55
    assert result.top_positive_factors

    updated_snapshot = apply_score_to_screener_factor_snapshot(
        screener_factor_snapshot=snapshot,
        score_result=result,
        target_v2_list_type=result.v2_list_type,
        target_screener_score=result.screener_score,
        quality_penalty_applied=False,
        quality_note=None,
    )

    assert updated_snapshot.composite_score is not None
    assert updated_snapshot.composite_score.v2_list_type == "READY_TO_BUY"
    assert updated_snapshot.selection_decision is not None
    assert updated_snapshot.selection_decision.list_type == "BUY_CANDIDATE"
    assert updated_snapshot.selection_decision.top_positive_factors


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
