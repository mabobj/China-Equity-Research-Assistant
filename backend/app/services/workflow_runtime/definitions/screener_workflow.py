"""Screener workflow definition."""

from __future__ import annotations

from typing import Any

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import ScreenerWorkflowRunRequest
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotDailyDataset,
    ScreenerSnapshotParams,
)
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.screener_service.pipeline import ScreenerPipeline
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext


class ScreenerWorkflowDefinitionBuilder:
    """Build the lightweight screener workflow definition."""

    def __init__(
        self,
        screener_pipeline: ScreenerPipeline,
        screener_snapshot_daily: ScreenerSnapshotDailyDataset,
    ) -> None:
        self._screener_pipeline = screener_pipeline
        self._screener_snapshot_daily = screener_snapshot_daily

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
        run_date = resolve_last_closed_trading_day()
        snapshot_params = ScreenerSnapshotParams(
            workflow_name="screener_run",
            max_symbols=request.max_symbols,
            top_n=request.top_n,
        )

        if not bool(request.force_refresh):
            cached = self._screener_snapshot_daily.load(
                run_date=run_date,
                params=snapshot_params,
            )
            if cached is not None:
                payload = cached.payload.model_copy(
                    update={
                        "freshness_mode": cached.freshness_mode,
                        "source_mode": cached.source_mode,
                    }
                )
                context.set_output("ScreenerRun", payload)
                return payload

        response = self._screener_pipeline.run_screener(
            max_symbols=request.max_symbols,
            top_n=request.top_n,
            force_refresh=bool(request.force_refresh),
        )
        saved = self._screener_snapshot_daily.save(
            run_date=run_date,
            params=snapshot_params,
            payload=response.model_copy(
                update={
                    "freshness_mode": response.freshness_mode or "computed",
                    "source_mode": response.source_mode or "pipeline",
                }
            ),
        )
        payload = saved.payload.model_copy(
            update={
                "freshness_mode": saved.freshness_mode,
                "source_mode": saved.source_mode,
            }
        )
        context.set_output("ScreenerRun", payload)
        return payload

    def _build_request_summary(
        self,
        request: ScreenerWorkflowRunRequest,
    ) -> dict[str, Any]:
        return {
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "force_refresh": request.force_refresh,
            "start_from": request.start_from,
            "stop_after": request.stop_after,
        }

    def _build_request_input_summary(self, context: WorkflowContext) -> dict[str, Any]:
        request = self._get_request(context)
        return {
            "max_symbols": request.max_symbols,
            "top_n": request.top_n,
            "force_refresh": request.force_refresh,
        }

    def _build_screener_summary(self, output: ScreenerRunResponse) -> dict[str, Any]:
        return {
            "as_of_date": output.as_of_date.isoformat(),
            "freshness_mode": output.freshness_mode,
            "source_mode": output.source_mode,
            "total_symbols": output.total_symbols,
            "scanned_symbols": output.scanned_symbols,
            "ready_to_buy_count": len(output.ready_to_buy_candidates),
            "watch_count": len(output.watch_candidates),
            "avoid_count": len(output.avoid_candidates),
        }

    def _build_final_output(self, context: WorkflowContext) -> ScreenerRunResponse:
        return context.require_output("ScreenerRun", ScreenerRunResponse)

    def _get_request(self, context: WorkflowContext) -> ScreenerWorkflowRunRequest:
        return context.request_as(ScreenerWorkflowRunRequest)


def build_screener_workflow_definition(
    *,
    screener_pipeline: ScreenerPipeline,
    screener_snapshot_daily: ScreenerSnapshotDailyDataset,
) -> WorkflowDefinition:
    """Build the screener workflow definition."""
    return ScreenerWorkflowDefinitionBuilder(
        screener_pipeline=screener_pipeline,
        screener_snapshot_daily=screener_snapshot_daily,
    ).build()
