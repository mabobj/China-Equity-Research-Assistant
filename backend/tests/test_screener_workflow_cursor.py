"""Screener workflow 游标与 17:00 重置测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import app.services.workflow_runtime.definitions.screener_workflow as screener_workflow_module
from app.schemas.market_data import UniverseItem, UniverseResponse
from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import ScreenerWorkflowRunRequest
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import SCREENER_SNAPSHOT_DAILY
from app.services.lineage_service.utils import build_lineage_metadata
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.executor import WorkflowExecutor


class _StubMarketDataService:
    def __init__(self) -> None:
        self._cursor: dict[str, Optional[str]] = {}
        self._items = [
            UniverseItem(
                symbol=f"{index:06d}.SZ",
                code=f"{index:06d}",
                exchange="SZ",
                name=f"股票{index}",
                source="stub",
            )
            for index in range(1, 6)
        ]

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(count=len(self._items), items=self._items)

    def get_refresh_cursor(self, cursor_key: str) -> Optional[str]:
        return self._cursor.get(cursor_key)

    def set_refresh_cursor(self, cursor_key: str, cursor_value: Optional[str]) -> None:
        self._cursor[cursor_key] = cursor_value


class _StubScreenerSnapshotDaily:
    def __init__(
        self,
        *,
        load_result: DataProductResult[ScreenerRunResponse] | None = None,
    ) -> None:
        self.load_result = load_result
        self.load_calls = 0

    def load(self, *, run_date, params):
        self.load_calls += 1
        return self.load_result

    def save(self, *, run_date, params, payload: ScreenerRunResponse):
        return DataProductResult(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class _StubScreenerSelectionSnapshotDaily:
    def __init__(self) -> None:
        self.save_calls = 0

    def save(self, *, run_date, params, payload: ScreenerRunResponse, lineage_metadata=None):
        self.save_calls += 1
        return DataProductResult(
            dataset="screener_selection_snapshot_daily",
            symbol=params.workflow_name,
            as_of_date=run_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
            lineage_metadata=(
                lineage_metadata.model_dump(mode="json")
                if hasattr(lineage_metadata, "model_dump")
                else lineage_metadata
            ),
        )


class _StubLineageService:
    def __init__(self) -> None:
        self.register_calls = 0

    def register_data_product(self, result) -> None:
        self.register_calls += 1


class _StubScreenerPipeline:
    def __init__(self) -> None:
        self.last_scan_symbols: list[str] = []

    def run_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
        force_refresh: bool = False,
        scan_items: Optional[list[UniverseItem]] = None,
        total_symbols_override: Optional[int] = None,
        run_context: Optional[dict[str, object]] = None,
    ) -> ScreenerRunResponse:
        selected = scan_items or []
        self.last_scan_symbols = [item.symbol for item in selected]
        if isinstance(run_context, dict):
            run_context.setdefault("screener_factor_snapshot_refs", [])
        return ScreenerRunResponse(
            as_of_date=date(2026, 3, 30),
            freshness_mode="computed",
            source_mode="pipeline",
            total_symbols=total_symbols_override or len(selected),
            scanned_symbols=len(selected),
            buy_candidates=[],
            watch_candidates=[],
            avoid_candidates=[],
            ready_to_buy_candidates=[],
            watch_pullback_candidates=[],
            watch_breakout_candidates=[],
            research_only_candidates=[],
        )


def test_screener_workflow_before_1700_exhausted_returns_empty(monkeypatch, tmp_path) -> None:
    _patch_now(monkeypatch, datetime(2026, 3, 30, 16, 59, tzinfo=screener_workflow_module._SHANGHAI_TZ))
    market_data_service = _StubMarketDataService()
    market_data_service.set_refresh_cursor(
        screener_workflow_module._CURSOR_SYMBOL_KEY,
        "000005.SZ",
    )
    market_data_service.set_refresh_cursor(
        screener_workflow_module._CURSOR_LAST_RESET_DATE_KEY,
        "2026-03-29",
    )
    pipeline = _StubScreenerPipeline()
    definition = screener_workflow_module.build_screener_workflow_definition(
        screener_pipeline=pipeline,
        screener_snapshot_daily=_StubScreenerSnapshotDaily(),
        screener_selection_snapshot_daily=_StubScreenerSelectionSnapshotDaily(),
        market_data_service=market_data_service,
        lineage_service=_StubLineageService(),
    )
    executor = WorkflowExecutor(artifact_store=FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(definition, ScreenerWorkflowRunRequest(batch_size=2))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.scanned_symbols == 0
    assert result.final_output.source_mode == "cursor_exhausted"
    assert pipeline.last_scan_symbols == []


def test_screener_workflow_after_1700_resets_cursor_and_runs_from_start(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_now(monkeypatch, datetime(2026, 3, 30, 17, 1, tzinfo=screener_workflow_module._SHANGHAI_TZ))
    market_data_service = _StubMarketDataService()
    market_data_service.set_refresh_cursor(
        screener_workflow_module._CURSOR_SYMBOL_KEY,
        "000005.SZ",
    )
    market_data_service.set_refresh_cursor(
        screener_workflow_module._CURSOR_LAST_RESET_DATE_KEY,
        "2026-03-29",
    )
    pipeline = _StubScreenerPipeline()
    definition = screener_workflow_module.build_screener_workflow_definition(
        screener_pipeline=pipeline,
        screener_snapshot_daily=_StubScreenerSnapshotDaily(),
        screener_selection_snapshot_daily=_StubScreenerSelectionSnapshotDaily(),
        market_data_service=market_data_service,
        lineage_service=_StubLineageService(),
    )
    executor = WorkflowExecutor(artifact_store=FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(definition, ScreenerWorkflowRunRequest(batch_size=2))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.scanned_symbols == 2
    assert pipeline.last_scan_symbols == ["000001.SZ", "000002.SZ"]
    assert (
        market_data_service.get_refresh_cursor(screener_workflow_module._CURSOR_SYMBOL_KEY)
        == "000002.SZ"
    )
    assert (
        market_data_service.get_refresh_cursor(
            screener_workflow_module._CURSOR_LAST_RESET_DATE_KEY
        )
        == "2026-03-30"
    )


def test_screener_workflow_manual_reset_invalidates_same_day_snapshot(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_now(
        monkeypatch,
        datetime(2026, 3, 30, 10, 1, tzinfo=screener_workflow_module._SHANGHAI_TZ),
    )
    market_data_service = _StubMarketDataService()
    market_data_service.set_refresh_cursor(
        screener_workflow_module._CURSOR_SNAPSHOT_INVALIDATED_DATE_KEY,
        "2026-03-30",
    )
    pipeline = _StubScreenerPipeline()
    cached_payload = ScreenerRunResponse(
        as_of_date=date(2026, 3, 30),
        freshness_mode="cache_hit",
        source_mode="snapshot",
        total_symbols=5,
        scanned_symbols=1,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[],
        research_only_candidates=[],
    )
    snapshot_dataset = _StubScreenerSnapshotDaily(
        load_result=DataProductResult(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol="screener_run",
            as_of_date=date(2026, 3, 30),
            payload=cached_payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )
    )
    definition = screener_workflow_module.build_screener_workflow_definition(
        screener_pipeline=pipeline,
        screener_snapshot_daily=snapshot_dataset,
        screener_selection_snapshot_daily=_StubScreenerSelectionSnapshotDaily(),
        market_data_service=market_data_service,
        lineage_service=_StubLineageService(),
    )
    executor = WorkflowExecutor(artifact_store=FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(definition, ScreenerWorkflowRunRequest(batch_size=2))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.scanned_symbols == 2
    assert pipeline.last_scan_symbols == ["000001.SZ", "000002.SZ"]
    assert snapshot_dataset.load_calls == 0


def test_screener_workflow_persists_selection_snapshot_and_registers_lineage(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_now(monkeypatch, datetime(2026, 3, 30, 17, 5, tzinfo=screener_workflow_module._SHANGHAI_TZ))
    market_data_service = _StubMarketDataService()
    pipeline = _StubScreenerPipeline()
    selection_dataset = _StubScreenerSelectionSnapshotDaily()
    lineage_service = _StubLineageService()
    definition = screener_workflow_module.build_screener_workflow_definition(
        screener_pipeline=pipeline,
        screener_snapshot_daily=_StubScreenerSnapshotDaily(),
        screener_selection_snapshot_daily=selection_dataset,
        market_data_service=market_data_service,
        lineage_service=lineage_service,
    )
    executor = WorkflowExecutor(artifact_store=FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(definition, ScreenerWorkflowRunRequest(batch_size=2))

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.scanned_symbols == 2
    assert selection_dataset.save_calls == 1
    assert lineage_service.register_calls == 1


def _patch_now(monkeypatch, value: datetime) -> None:
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return value.replace(tzinfo=None)
            return value.astimezone(tz)

    monkeypatch.setattr(screener_workflow_module, "datetime", _FixedDateTime)
