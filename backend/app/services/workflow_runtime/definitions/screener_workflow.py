"""Screener workflow definition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import ScreenerWorkflowRunRequest
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotDailyDataset,
    ScreenerSnapshotParams,
)
from app.services.data_service.market_data_service import MarketDataService
from app.services.screener_service.pipeline import ScreenerPipeline
from app.services.screener_service.texts import ensure_chinese_short_reason
from app.services.screener_service.universe import load_scan_universe
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_CURSOR_SYMBOL_KEY = "screener_run_cursor_symbol"
_CURSOR_LAST_RESET_DATE_KEY = "screener_run_cursor_last_reset_date"
_DEFAULT_BATCH_SIZE = 50


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
        market_data_service: MarketDataService,
    ) -> None:
        self._screener_pipeline = screener_pipeline
        self._screener_snapshot_daily = screener_snapshot_daily
        self._market_data_service = market_data_service

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
        batch_size = self._resolve_batch_size(request)
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
                as_of_date=now.date(),
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
            )
            context.set_output("ScreenerRun", payload)
            return payload

        snapshot_params = ScreenerSnapshotParams(
            workflow_name="screener_run",
            max_symbols=request.max_symbols,
            top_n=request.top_n,
            batch_size=batch_size,
            cursor_start_symbol=selection.cursor_start_symbol,
            cursor_start_index=selection.start_index,
            reset_trade_date=now.date().isoformat(),
        )
        if not bool(request.force_refresh):
            cached = self._screener_snapshot_daily.load(
                run_date=now.date(),
                params=snapshot_params,
            )
            if cached is not None:
                payload = cached.payload.model_copy(
                    update={
                        "freshness_mode": cached.freshness_mode,
                        "source_mode": cached.source_mode,
                    }
                )
                self._advance_cursor_after_success(selection.selected_items)
                context.set_output("ScreenerRun", payload)
                return payload

        response = self._screener_pipeline.run_screener(
            max_symbols=request.max_symbols,
            top_n=request.top_n,
            force_refresh=bool(request.force_refresh),
            scan_items=selection.selected_items,
            total_symbols_override=total_symbols,
        )
        normalized_response = self._normalize_response(response)
        saved = self._screener_snapshot_daily.save(
            run_date=now.date(),
            params=snapshot_params,
            payload=normalized_response.model_copy(
                update={
                    "freshness_mode": normalized_response.freshness_mode or "computed",
                    "source_mode": normalized_response.source_mode or "pipeline",
                }
            ),
        )
        payload = saved.payload.model_copy(
            update={
                "freshness_mode": saved.freshness_mode,
                "source_mode": saved.source_mode,
            }
        )
        self._advance_cursor_after_success(selection.selected_items)
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
            warning_messages=[
                "17:00 后首次运行，游标已自动重置到股票池起点。"
            ]
            if reset_applied
            else [],
            reset_applied=reset_applied,
        )

    def _advance_cursor_after_success(self, selected_items: list[Any]) -> None:
        if not selected_items:
            return
        last_symbol = str(selected_items[-1].symbol).upper()
        self._market_data_service.set_refresh_cursor(_CURSOR_SYMBOL_KEY, last_symbol)

    def _normalize_response(self, response: ScreenerRunResponse) -> ScreenerRunResponse:
        def _normalize_candidates(candidates):
            normalized = []
            for candidate in candidates:
                short_reason = ensure_chinese_short_reason(
                    list_type=candidate.v2_list_type,
                    short_reason=candidate.short_reason,
                )
                if short_reason == candidate.short_reason:
                    normalized.append(candidate)
                    continue
                normalized.append(candidate.model_copy(update={"short_reason": short_reason}))
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
        }

    def _build_request_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        request = self._get_request(context)
        return {
            "batch_size": self._resolve_batch_size(request),
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "force_refresh": request.force_refresh,
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


def build_screener_workflow_definition(
    *,
    screener_pipeline: ScreenerPipeline,
    screener_snapshot_daily: ScreenerSnapshotDailyDataset,
    market_data_service: MarketDataService,
) -> WorkflowDefinition:
    """Build the screener workflow definition."""
    return ScreenerWorkflowDefinitionBuilder(
        screener_pipeline=screener_pipeline,
        screener_snapshot_daily=screener_snapshot_daily,
        market_data_service=market_data_service,
    ).build()
