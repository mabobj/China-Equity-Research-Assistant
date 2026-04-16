from datetime import date, timedelta

from app.schemas.market_data import DailyBar
from app.services.feature_service.screener_factor_service import ScreenerFactorService
from app.services.screener_service.cross_section_factor_service import CrossSectionFactorService


def test_screener_factor_service_populates_continuity_fields() -> None:
    snapshot = ScreenerFactorService().build_snapshot_from_bars(
        symbol="600519.SH",
        bars=_build_bars(
            symbol="600519.SH",
            length=160,
            close_start=100.0,
            close_step=0.65,
            amount=150_000_000.0,
        ),
        industry="Consumer",
        list_date=date(2001, 8, 27),
        is_st=False,
        is_suspended=False,
    )

    assert snapshot.cross_section_factors.trend_score_raw is not None
    assert snapshot.cross_section_factors.trend_score_raw >= 60
    assert snapshot.cross_section_factors.trend_persistence_5d is not None
    assert snapshot.cross_section_factors.liquidity_persistence_5d is not None
    assert snapshot.cross_section_factors.breakout_readiness_persistence_5d is not None
    assert snapshot.cross_section_factors.volatility_regime_stability is not None
    assert snapshot.cross_section_factors.industry_bucket == "Consumer"


def test_cross_section_factor_service_enriches_rank_features() -> None:
    factor_service = ScreenerFactorService()
    snapshots = [
        factor_service.build_snapshot_from_bars(
            symbol="600519.SH",
            bars=_build_bars(
                symbol="600519.SH",
                length=160,
                close_start=100.0,
                close_step=0.70,
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
    by_symbol = {snapshot.symbol: snapshot for snapshot in enriched}

    assert by_symbol["600519.SH"].cross_section_factors.universe_size == 3
    assert by_symbol["600519.SH"].cross_section_factors.amount_rank_pct == 1.0
    assert by_symbol["600519.SH"].cross_section_factors.return_20d_rank_pct == 1.0
    assert by_symbol["300750.SZ"].cross_section_factors.return_20d_rank_pct < 0.5
    assert by_symbol["600519.SH"].cross_section_factors.industry_relative_strength_rank_pct == 1.0
    assert by_symbol["000001.SZ"].cross_section_factors.trend_score_rank_pct is not None


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
        high = close * 1.012
        low = close * 0.988
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start_date + timedelta(days=index),
                open=close * 0.997,
                high=high,
                low=low,
                close=close,
                volume=amount / close,
                amount=amount,
                source="stub",
            ),
        )
    return bars
