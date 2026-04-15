from datetime import date, timedelta

import pytest

from app.schemas.market_data import DailyBar
from app.services.data_service.exceptions import InsufficientDataError
from app.services.feature_service.screener_factor_service import ScreenerFactorService


def test_screener_factor_service_builds_process_metrics_and_atomic_factors() -> None:
    service = ScreenerFactorService()

    snapshot = service.build_snapshot_from_bars(
        symbol="600519.SH",
        bars=_build_bars(
            symbol="600519.SH",
            length=160,
            close_start=100.0,
            close_step=0.7,
            amount=180_000_000.0,
        ),
        name="KweichowMoutai",
        market="A",
        board="MainBoard",
        industry="Consumer",
        list_date=date(2001, 8, 27),
        is_st=False,
        is_suspended=False,
        provider_used="tdx_api",
        source_mode="local_plus_provider",
        freshness_mode="cache_preferred",
    )

    assert snapshot.symbol == "600519.SH"
    assert snapshot.process_metrics.ma_20 is not None
    assert snapshot.process_metrics.ma_60 is not None
    assert snapshot.process_metrics.return_20d is not None
    assert snapshot.process_metrics.atr_20_pct is not None
    assert snapshot.atomic_factors.basic_universe_eligibility is True
    assert snapshot.atomic_factors.close_above_ma20 is True
    assert snapshot.atomic_factors.close_above_ma60 is True
    assert snapshot.atomic_factors.ma20_above_ma60 is True
    assert snapshot.atomic_factors.trend_state_basic == "up"
    assert snapshot.atomic_factors.liquidity_pass is True
    assert snapshot.provider_used == "tdx_api"
    assert snapshot.dataset_version.endswith(":600519.SH:v1")


def test_screener_factor_service_marks_new_listing_and_low_liquidity_risk() -> None:
    service = ScreenerFactorService()
    as_of_date = date(2026, 4, 16)

    snapshot = service.build_snapshot_from_bars(
        symbol="301000.SZ",
        bars=_build_bars(
            symbol="301000.SZ",
            length=90,
            start_date=as_of_date - timedelta(days=89),
            close_start=18.0,
            close_step=0.08,
            amount=8_000_000.0,
        ),
        list_date=as_of_date - timedelta(days=80),
        is_st=False,
        is_suspended=False,
    )

    assert snapshot.atomic_factors.is_new_listing_risk is True
    assert snapshot.atomic_factors.liquidity_pass is False
    assert snapshot.atomic_factors.amount_level_state == "low"
    assert snapshot.atomic_factors.basic_universe_eligibility is False


def test_screener_factor_service_requires_minimum_bar_history() -> None:
    service = ScreenerFactorService()

    with pytest.raises(InsufficientDataError):
        service.build_snapshot_from_bars(
            symbol="000001.SZ",
            bars=_build_bars(
                symbol="000001.SZ",
                length=40,
                close_start=10.0,
                close_step=0.1,
                amount=50_000_000.0,
            ),
        )


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
        close = close_start + close_step * index
        high = close * 1.01
        low = close * 0.99
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start_date + timedelta(days=index),
                open=close * 0.998,
                high=high,
                low=low,
                close=close,
                volume=amount / close,
                amount=amount,
                source="stub",
            ),
        )
    return bars
