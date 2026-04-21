"""Screener workflow definition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import logging
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import ScreenerWorkflowRunRequest
from app.services.data_products.catalog import SCREENER_SELECTION_SNAPSHOT_DAILY
from app.services.data_products.datasets.screener_selection_snapshot_daily import (
    ScreenerSelectionSnapshotDailyDataset,
)
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotDailyDataset,
    ScreenerSnapshotParams,
)
from app.services.data_service.market_data_service import MarketDataService
from app.services.lineage_service.lineage_service import LineageService
from app.services.lineage_service.utils import (
    build_dependency,
    build_lineage_metadata,
    build_source_ref,
)
from app.services.screener_service.pipeline import ScreenerPipeline
from app.services.screener_service.scheme_service import ScreenerSchemeService
from app.services.screener_service.texts import ensure_chinese_short_reason
from app.services.screener_service.universe import load_scan_universe
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_CURSOR_SYMBOL_KEY = "screener_run_cursor_symbol"
_CURSOR_LAST_RESET_DATE_KEY = "screener_run_cursor_last_reset_date"
_CURSOR_SNAPSHOT_INVALIDATED_DATE_KEY = "screener_run_snapshot_invalidated_date"
_DEFAULT_BATCH_SIZE = 50
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreenerCursorSelection:
    selected_items: list[Any]
    start_index: int
    cursor_start_symbol: str | None
    warning_messages: list[str]
    reset_applied: bool


class ScreenerWorkflowDefinitionBuilder:
    """Build the lightweight screener workflow definition."""

    def __init__(
        self,
        screener_pipeline: ScreenerPipeline,
        screener_snapshot_daily: ScreenerSnapshotDailyDataset,
        screener_selection_snapshot_daily: ScreenerSelectionSnapshotDailyDataset,
        market_data_service: MarketDataService,
        lineage_service: LineageService,
        scheme_service: ScreenerSchemeService | None = None,
    ) -> None:
        self._screener_pipeline = screener_pipeline
        self._screener_snapshot_daily = screener_snapshot_daily
        self._screener_selection_snapshot_daily = screener_selection_snapshot_daily
        self._market_data_service = market_data_service
        self._lineage_service = lineage_service
        self._scheme_service = scheme_service

    def build(self) -> WorkflowDefinition:
        return WorkflowDefinition(
            name="screener_run",
            request_contract=ScreenerWorkflowRunRequest,
            final_output_contract=ScreenerRunResponse,
            nodes=(
                WorkflowNode(
                    name="ScreenerRun",
                    input_contract=ScreenerWorkflowRunRequest,
                    output_contract=ScreenerRunResponse,
                    handler=self._run_screener,
                    input_summary_builder=self._build_request_input_summary,
                    output_summary_builder=self._build_screener_summary,
                ),
            ),
            input_summary_builder=self._build_request_summary,
            final_output_builder=self._build_final_output,
            final_output_summary_builder=self._build_screener_summary,
        )

    def _run_screener(self, context: WorkflowContext) -> ScreenerRunResponse:
        request = self._get_request(context)
        now = datetime.now(_SHANGHAI_TZ)
        current_date = now.date()
        batch_size = self._resolve_batch_size(request)
        started_at = perf_counter()
        total_symbols, universe_items = load_scan_universe(
            market_data_service=self._market_data_service,
            max_symbols=None,
        )
        selection = self._select_items_for_batch(
            universe_items=universe_items,
            batch_size=batch_size,
            now=now,
        )
        context.set_meta("warning_messages", list(selection.warning_messages))

        if not selection.selected_items:
            payload = ScreenerRunResponse(
                as_of_date=current_date,
                freshness_mode="cache_preferred",
                source_mode="cursor_exhausted",
                total_symbols=total_symbols,
                scanned_symbols=0,
                buy_candidates=[],
                watch_candidates=[],
                avoid_candidates=[],
                ready_to_buy_candidates=[],
                watch_pullback_candidates=[],
                watch_breakout_candidates=[],
                research_only_candidates=[],
                scheme_id=request.scheme_id,
                scheme_version=request.scheme_version,
            )
            context.set_output("ScreenerRun", payload)
            return payload

        scheme_run_context = (
            self._scheme_service.load_run_context(context.run_id)
            if self._scheme_service is not None
            else None
        )
        scheme_metadata = _build_scheme_runtime_metadata(scheme_run_context)
        snapshot_params = ScreenerSnapshotParams(
            workflow_name="screener_run",
            max_symbols=request.max_symbols,
            top_n=request.top_n,
            batch_size=batch_size,
            cursor_start_symbol=selection.cursor_start_symbol,
            cursor_start_index=selection.start_index,
            reset_trade_date=current_date.isoformat(),
            scheme_id=scheme_metadata["scheme_id"],
            scheme_version=scheme_metadata["scheme_version"],
            scheme_name=scheme_metadata["scheme_name"],
            scheme_snapshot_hash=scheme_metadata["scheme_snapshot_hash"],
        )
        snapshot_invalidated_today = self._is_snapshot_invalidated_for_date(
            current_date=current_date
        )
        logger.info(
            "event=screener.run.selection run_id=%s workflow=%s batch_size=%s total_symbols=%s selected_symbols=%s cursor_start_symbol=%s cursor_start_index=%s snapshot_invalidated_today=%s force_refresh=%s",
            context.run_id,
            context.workflow_name,
            batch_size,
            total_symbols,
            len(selection.selected_items),
            selection.cursor_start_symbol,
            selection.start_index,
            snapshot_invalidated_today,
            bool(request.force_refresh),
        )
        if snapshot_invalidated_today:
            warning_messages = list(context.get_meta("warning_messages") or [])
            warning_messages.append(
                "检测到当日游标重置：今日初筛快照已作废，将按游标分批重新计算。"
            )
            context.set_meta("warning_messages", warning_messages)

        if not bool(request.force_refresh) and not snapshot_invalidated_today:
            cached = self._screener_snapshot_daily.load(
                run_date=current_date,
                params=snapshot_params,
            )
            if cached is not None:
                logger.info(
                    "event=screener.run.snapshot_hit run_id=%s workflow=%s as_of_date=%s selected_symbols=%s source_mode=%s freshness_mode=%s",
                    context.run_id,
                    context.workflow_name,
                    current_date.isoformat(),
                    len(selection.selected_items),
                    cached.source_mode,
                    cached.freshness_mode,
                )
                payload = cached.payload.model_copy(
                    update={
                        "freshness_mode": cached.freshness_mode,
                        "source_mode": cached.source_mode,
                    }
                )
                self._advance_cursor_after_success(selection.selected_items)
                context.set_output("ScreenerRun", payload)
                return payload

        pipeline_run_context = {
            "run_id": context.run_id,
            "workflow_name": context.workflow_name,
            "batch_size": batch_size,
            "cursor_start_symbol": selection.cursor_start_symbol,
            "cursor_start_index": selection.start_index,
            "reset_trade_date": current_date.isoformat(),
            "screener_factor_snapshot_refs": [],
            **scheme_metadata,
        }
        response = self._screener_pipeline.run_screener(
            max_symbols=request.max_symbols,
            top_n=request.top_n,
            force_refresh=bool(request.force_refresh),
            scan_items=selection.selected_items,
            total_symbols_override=total_symbols,
            run_context=pipeline_run_context,
        )
        normalized_response = self._normalize_response(response)
        normalized_payload = normalized_response.model_copy(
            update={
                "freshness_mode": normalized_response.freshness_mode or "computed",
                "source_mode": normalized_response.source_mode or "pipeline",
                **scheme_metadata,
            }
        )
        saved = self._screener_snapshot_daily.save(
            run_date=current_date,
            params=snapshot_params,
            payload=normalized_payload,
        )
        selection_saved = self._screener_selection_snapshot_daily.save(
            run_date=current_date,
            params=snapshot_params,
            payload=normalized_payload,
            lineage_metadata=self._build_selection_lineage_metadata(
                run_date=current_date,
                params=snapshot_params,
                run_context=pipeline_run_context,
            ),
        )
        payload = saved.payload.model_copy(
            update={
                "freshness_mode": saved.freshness_mode,
                "source_mode": saved.source_mode,
            }
        )
        self._lineage_service.register_data_product(selection_saved)
        self._advance_cursor_after_success(selection.selected_items)
        logger.info(
            "event=screener.run.result_persisted run_id=%s workflow=%s as_of_date=%s scanned_symbols=%s ready_count=%s watch_count=%s avoid_count=%s elapsed_ms=%s",
            context.run_id,
            context.workflow_name,
            payload.as_of_date.isoformat(),
            payload.scanned_symbols,
            len(payload.ready_to_buy_candidates),
            len(payload.watch_candidates),
            len(payload.avoid_candidates),
            int((perf_counter() - started_at) * 1000),
        )
        context.set_output("ScreenerRun", payload)
        return payload

    def _select_items_for_batch(
        self,
        *,
        universe_items: list[Any],
        batch_size: int,
        now: datetime,
    ) -> ScreenerCursorSelection:
        if not universe_items:
            return ScreenerCursorSelection(
                selected_items=[],
                start_index=0,
                cursor_start_symbol=None,
                warning_messages=["股票池为空，当前无需执行初筛。"],
                reset_applied=False,
            )

        current_date = now.date()
        after_1700 = now.time() >= time(17, 0)
        cursor_symbol = self._market_data_service.get_refresh_cursor(_CURSOR_SYMBOL_KEY)
        reset_date_raw = self._market_data_service.get_refresh_cursor(
            _CURSOR_LAST_RESET_DATE_KEY
        )
        reset_applied = False
        if after_1700 and reset_date_raw != current_date.isoformat():
            cursor_symbol = None
            self._market_data_service.set_refresh_cursor(_CURSOR_SYMBOL_KEY, None)
            self._market_data_service.set_refresh_cursor(
                _CURSOR_LAST_RESET_DATE_KEY, current_date.isoformat()
            )
            reset_applied = True

        symbols = [str(item.symbol).upper() for item in universe_items]
        symbol_to_index = {symbol: index for index, symbol in enumerate(symbols)}

        start_index = 0
        if cursor_symbol:
            cursor_index = symbol_to_index.get(cursor_symbol.upper())
            if cursor_index is not None:
                if cursor_index >= len(universe_items) - 1:
                    if after_1700 and reset_applied:
                        start_index = 0
                    else:
                        return ScreenerCursorSelection(
                            selected_items=[],
                            start_index=0,
                            cursor_start_symbol=None,
                            warning_messages=[
                                "当前窗口的股票已全部计算完成，请等待下一个 17:00 窗口。"
                            ],
                            reset_applied=reset_applied,
                        )
                else:
                    start_index = cursor_index + 1

        end_index = min(start_index + batch_size, len(universe_items))
        selected_items = universe_items[start_index:end_index]
        return ScreenerCursorSelection(
            selected_items=selected_items,
            start_index=start_index,
            cursor_start_symbol=selected_items[0].symbol if selected_items else None,
            warning_messages=["17:00 后首次运行，游标已自动重置到股票池起点。"]
            if reset_applied
            else [],
            reset_applied=reset_applied,
        )

    def _advance_cursor_after_success(self, selected_items: list[Any]) -> None:
        if not selected_items:
            return
        last_symbol = str(selected_items[-1].symbol).upper()
        self._market_data_service.set_refresh_cursor(_CURSOR_SYMBOL_KEY, last_symbol)
        logger.info(
            "event=screener.run.cursor_advanced cursor_symbol=%s scanned_count=%s",
            last_symbol,
            len(selected_items),
        )

    def _normalize_response(self, response: ScreenerRunResponse) -> ScreenerRunResponse:
        def _normalize_candidates(candidates: list[Any]) -> list[Any]:
            normalized = []
            for candidate in candidates:
                short_reason = ensure_chinese_short_reason(
                    list_type=candidate.v2_list_type,
                    short_reason=candidate.short_reason,
                )
                if short_reason == candidate.short_reason:
                    normalized.append(candidate)
                    continue
                normalized.append(
                    candidate.model_copy(update={"short_reason": short_reason})
                )
            return normalized

        return response.model_copy(
            update={
                "buy_candidates": _normalize_candidates(response.buy_candidates),
                "watch_candidates": _normalize_candidates(response.watch_candidates),
                "avoid_candidates": _normalize_candidates(response.avoid_candidates),
                "ready_to_buy_candidates": _normalize_candidates(
                    response.ready_to_buy_candidates
                ),
                "watch_pullback_candidates": _normalize_candidates(
                    response.watch_pullback_candidates
                ),
                "watch_breakout_candidates": _normalize_candidates(
                    response.watch_breakout_candidates
                ),
                "research_only_candidates": _normalize_candidates(
                    response.research_only_candidates
                ),
            }
        )

    def _build_request_summary(
        self,
        request: ScreenerWorkflowRunRequest,
    ) -> dict[str, Any]:
        return {
            "batch_size": self._resolve_batch_size(request),
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "force_refresh": request.force_refresh,
            "start_from": request.start_from,
            "stop_after": request.stop_after,
            "scheme_id": request.scheme_id,
            "scheme_version": request.scheme_version,
        }

    def _build_request_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        request = self._get_request(context)
        return {
            "batch_size": self._resolve_batch_size(request),
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "force_refresh": request.force_refresh,
            "scheme_id": request.scheme_id,
            "scheme_version": request.scheme_version,
        }

    def _build_screener_summary(self, output: ScreenerRunResponse) -> dict[str, Any]:
        summary = {
            "as_of_date": output.as_of_date.isoformat(),
            "freshness_mode": output.freshness_mode,
            "source_mode": output.source_mode,
            "total_symbols": output.total_symbols,
            "scanned_symbols": output.scanned_symbols,
            "ready_to_buy_count": len(output.ready_to_buy_candidates),
            "watch_count": len(output.watch_candidates),
            "avoid_count": len(output.avoid_candidates),
        }
        if output.scanned_symbols == 0 and output.source_mode == "cursor_exhausted":
            summary["warning_messages"] = [
                "当前窗口已无待计算股票，请等待下一个 17:00 窗口。"
            ]
        return summary

    def _build_final_output(self, context: WorkflowContext) -> ScreenerRunResponse:
        return context.require_output("ScreenerRun", ScreenerRunResponse)

    def _resolve_batch_size(self, request: ScreenerWorkflowRunRequest) -> int:
        if request.batch_size is not None:
            return request.batch_size
        if request.max_symbols is not None:
            return request.max_symbols
        return _DEFAULT_BATCH_SIZE

    def _get_request(self, context: WorkflowContext) -> ScreenerWorkflowRunRequest:
        return context.request_as(ScreenerWorkflowRunRequest)

    def _is_snapshot_invalidated_for_date(self, *, current_date: date) -> bool:
        marker = self._market_data_service.get_refresh_cursor(
            _CURSOR_SNAPSHOT_INVALIDATED_DATE_KEY
        )
        if not isinstance(marker, str) or not marker:
            return False
        return marker == current_date.isoformat()

    def _build_selection_lineage_metadata(
        self,
        *,
        run_date: date,
        params: ScreenerSnapshotParams,
        run_context: dict[str, object],
    ):
        factor_refs = run_context.get("screener_factor_snapshot_refs")
        dependencies = []
        if isinstance(factor_refs, list):
            for item in factor_refs:
                if not isinstance(item, dict):
                    continue
                dataset = item.get("dataset")
                dataset_version = item.get("dataset_version")
                as_of_date = item.get("as_of_date")
                if not isinstance(dataset, str) or not isinstance(dataset_version, str):
                    continue
                if not isinstance(as_of_date, date):
                    continue
                dependencies.append(
                    build_dependency(
                        "screener_factor_snapshot",
                        build_source_ref(
                            dataset=dataset,
                            dataset_version=dataset_version,
                            symbol=(
                                str(item.get("symbol"))
                                if item.get("symbol") is not None
                                else None
                            ),
                            as_of_date=as_of_date,
                            provider_used=(
                                str(item.get("provider_used"))
                                if item.get("provider_used") is not None
                                else None
                            ),
                            source_mode=(
                                str(item.get("source_mode"))
                                if item.get("source_mode") is not None
                                else None
                            ),
                            freshness_mode=(
                                str(item.get("freshness_mode"))
                                if item.get("freshness_mode") is not None
                                else None
                            ),
                            updated_at=item.get("updated_at"),
                        ),
                    )
                )
        dataset_version = (
            f"{SCREENER_SELECTION_SNAPSHOT_DAILY}:{run_date.isoformat()}:{params.workflow_name}:v1"
        )
        warning_messages: list[str] = []
        if not dependencies:
            warning_messages.append(
                "selection snapshot 缺少直接 factor snapshot 依赖记录。"
            )
        return build_lineage_metadata(
            dataset=SCREENER_SELECTION_SNAPSHOT_DAILY,
            dataset_version=dataset_version,
            as_of_date=run_date,
            symbol=params.workflow_name,
            dependencies=dependencies,
            warning_messages=warning_messages,
        )


def build_screener_workflow_definition(
    *,
    screener_pipeline: ScreenerPipeline,
    screener_snapshot_daily: ScreenerSnapshotDailyDataset,
    screener_selection_snapshot_daily: ScreenerSelectionSnapshotDailyDataset,
    market_data_service: MarketDataService,
    lineage_service: LineageService,
    scheme_service: ScreenerSchemeService | None = None,
) -> WorkflowDefinition:
    """Build the screener workflow definition."""
    return ScreenerWorkflowDefinitionBuilder(
        screener_pipeline=screener_pipeline,
        screener_snapshot_daily=screener_snapshot_daily,
        screener_selection_snapshot_daily=screener_selection_snapshot_daily,
        market_data_service=market_data_service,
        lineage_service=lineage_service,
        scheme_service=scheme_service,
    ).build()


def _build_scheme_runtime_metadata(
    snapshot,
) -> dict[str, object]:
    if snapshot is None:
        return {
            "scheme_id": None,
            "scheme_version": None,
            "scheme_name": None,
            "scheme_snapshot_hash": None,
            "selected_factor_groups": [],
            "scoring_profile_name": None,
            "quality_gate_profile_name": None,
        }
    factor_selection = snapshot.effective_scheme_config.factor_selection_config
    factor_weights = snapshot.effective_scheme_config.factor_weight_config
    quality_gate = snapshot.effective_scheme_config.quality_gate_config
    return {
        "scheme_id": snapshot.scheme_id,
        "scheme_version": snapshot.scheme_version,
        "scheme_name": snapshot.scheme_name,
        "scheme_snapshot_hash": snapshot.scheme_snapshot_hash,
        "selected_factor_groups": _normalize_string_list(
            factor_selection.get("enabled_groups")
            if isinstance(factor_selection, dict)
            else None
        ),
        "scoring_profile_name": (
            _string_or_none(factor_weights.get("profile_name"))
            if isinstance(factor_weights, dict)
            else None
        ),
        "quality_gate_profile_name": (
            _string_or_none(quality_gate.get("profile_name"))
            if isinstance(quality_gate, dict)
            else None
        ),
    }


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _string_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
