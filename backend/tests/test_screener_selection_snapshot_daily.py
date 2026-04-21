from __future__ import annotations

from datetime import date, datetime, timezone

from app.schemas.lineage import LineageMetadata
from app.schemas.screener import ScreenerRunResponse
from app.services.data_products.datasets.screener_selection_snapshot_daily import (
    ScreenerSelectionSnapshotDailyDataset,
)
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotParams,
)
from app.services.data_products.repository import DataProductRepository
from app.services.lineage_service.utils import build_lineage_metadata


def test_screener_selection_snapshot_daily_round_trip(tmp_path) -> None:
    repository = DataProductRepository(tmp_path / "daily_products")
    dataset = ScreenerSelectionSnapshotDailyDataset(repository=repository)
    payload = ScreenerRunResponse(
        as_of_date=date(2026, 4, 17),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=100,
        scanned_symbols=50,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[],
        research_only_candidates=[],
    )
    params = ScreenerSnapshotParams(
        workflow_name="screener_run",
        max_symbols=50,
        top_n=20,
        batch_size=50,
        cursor_start_symbol="000001.SZ",
        cursor_start_index=0,
        reset_trade_date="2026-04-17",
    )
    lineage_metadata = build_lineage_metadata(
        dataset="screener_selection_snapshot_daily",
        dataset_version="screener_selection_snapshot_daily:2026-04-17:screener_run:v1",
        as_of_date=date(2026, 4, 17),
        symbol="screener_run",
        dependencies=[],
        generated_at=datetime.now(timezone.utc),
    )

    saved = dataset.save(
        run_date=date(2026, 4, 17),
        params=params,
        payload=payload,
        lineage_metadata=lineage_metadata,
    )
    loaded = dataset.load(run_date=date(2026, 4, 17), params=params)

    assert saved.dataset == "screener_selection_snapshot_daily"
    assert saved.lineage_metadata is not None
    assert isinstance(saved.lineage_metadata, LineageMetadata)
    assert loaded is not None
    assert loaded.dataset == "screener_selection_snapshot_daily"
    assert loaded.lineage_metadata is not None
    assert loaded.lineage_metadata.dataset_version == lineage_metadata.dataset_version


def test_screener_selection_snapshot_params_hash_changes_with_scheme_metadata(
    tmp_path,
) -> None:
    repository = DataProductRepository(tmp_path / "daily_products")
    dataset = ScreenerSelectionSnapshotDailyDataset(repository=repository)
    base_params = ScreenerSnapshotParams(
        workflow_name="screener_run",
        max_symbols=50,
        top_n=20,
        batch_size=50,
        cursor_start_symbol="000001.SZ",
        cursor_start_index=0,
        reset_trade_date="2026-04-17",
    )
    scheme_params = ScreenerSnapshotParams(
        workflow_name="screener_run",
        max_symbols=50,
        top_n=20,
        batch_size=50,
        cursor_start_symbol="000001.SZ",
        cursor_start_index=0,
        reset_trade_date="2026-04-17",
        scheme_id="default_builtin_scheme",
        scheme_version="legacy_v1",
        scheme_name="默认内置方案",
        scheme_snapshot_hash="hash-001",
    )

    assert dataset._params_hash(base_params) != dataset._params_hash(scheme_params)
