from __future__ import annotations

from datetime import date, timedelta

from app.schemas.market_data import DailyBar
from app.services.data_products.datasets.screener_factor_snapshot_daily import (
    ScreenerFactorSnapshotDailyDataset,
    ScreenerFactorSnapshotParams,
)
from app.services.data_products.repository import DataProductRepository
from app.services.feature_service.screener_factor_service import ScreenerFactorService


def test_screener_factor_snapshot_daily_round_trip(tmp_path) -> None:
    repository = DataProductRepository(tmp_path / "daily_products")
    dataset = ScreenerFactorSnapshotDailyDataset(repository=repository)
    service = ScreenerFactorService()
    payload = service.build_snapshot_from_bars(
        symbol="600519.SH",
        bars=_build_bars("600519.SH"),
        name="贵州茅台",
        provider_used="mootdx",
        source_mode="local_plus_provider",
        freshness_mode="cache_hit",
    )
    params = ScreenerFactorSnapshotParams(
        workflow_name="screener_run",
        max_symbols=50,
        top_n=20,
        batch_size=50,
        cursor_start_symbol="600519.SH",
        cursor_start_index=0,
        reset_trade_date="2026-04-16",
    )

    saved = dataset.save("600519.SH", params=params, payload=payload)
    loaded = dataset.load("600519.SH", as_of_date=saved.as_of_date, params=params)

    assert saved.dataset == "screener_factor_snapshot_daily"
    assert saved.dataset_version == payload.dataset_version
    assert saved.provider_used == "mootdx"
    assert saved.lineage_metadata is not None
    assert loaded is not None
    assert loaded.dataset_version == payload.dataset_version
    assert loaded.payload.selection_decision is None
    assert loaded.lineage_metadata is not None
    assert loaded.lineage_metadata.dataset == "screener_factor_snapshot_daily"
    assert loaded.lineage_metadata.dependencies
    assert loaded.lineage_metadata.dependencies[0].role == "daily_bars_daily"


def _build_bars(symbol: str, length: int = 160) -> list[DailyBar]:
    start_date = date(2025, 9, 1)
    bars: list[DailyBar] = []
    for index in range(length):
        close = 100.0 + index * 0.6
        bars.append(
            DailyBar(
                symbol=symbol,
                trade_date=start_date + timedelta(days=index),
                open=close * 0.995,
                high=close * 1.012,
                low=close * 0.988,
                close=close,
                volume=1_500_000.0 + index * 1000.0,
                amount=(1_500_000.0 + index * 1000.0) * close,
                source="mootdx",
            )
        )
    return bars
