"""Screener workflow 互斥运行测试。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import time
from threading import Event

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import ScreenerWorkflowRunRequest
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry
from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService


def test_screener_workflow_run_is_mutex_when_existing_run_is_running(tmp_path) -> None:
    started_event = Event()
    release_event = Event()
    definition = _build_blocking_screener_definition(
        started_event=started_event,
        release_event=release_event,
    )
    artifact_store = FileWorkflowArtifactStore(tmp_path)
    background_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="test-workflow",
    )
    runtime_service = WorkflowRuntimeService(
        registry=WorkflowRegistry(definitions=(definition,)),
        executor=WorkflowExecutor(artifact_store=artifact_store),
        artifact_store=artifact_store,
        background_executor=background_executor,
    )

    try:
        first = runtime_service.run_screener_workflow(
            ScreenerWorkflowRunRequest(max_symbols=50, top_n=20)
        )
        assert first.status == "running"
        assert started_event.wait(timeout=1.5)

        second = runtime_service.run_screener_workflow(
            ScreenerWorkflowRunRequest(max_symbols=80, top_n=30)
        )
        assert second.status == "running"
        assert second.run_id == first.run_id
        assert any("已有运行中的初筛任务" in message for message in second.warning_messages)
    finally:
        release_event.set()
        background_executor.shutdown(wait=True)

    completed_status = None
    for _ in range(20):
        artifact = artifact_store.load_run(first.run_id)
        completed_status = artifact.status
        if completed_status != "running":
            break
        time.sleep(0.05)

    assert completed_status == "completed"


def _build_blocking_screener_definition(
    *,
    started_event: Event,
    release_event: Event,
) -> WorkflowDefinition:
    def _build_input_summary(request: ScreenerWorkflowRunRequest) -> dict:
        return {"max_symbols": request.max_symbols, "top_n": request.top_n}

    def _build_step_input(context) -> dict:
        request = context.request_as(ScreenerWorkflowRunRequest)
        return {"max_symbols": request.max_symbols, "top_n": request.top_n}

    def _run_screener(_context) -> ScreenerRunResponse:
        started_event.set()
        release_event.wait(timeout=2.0)
        return ScreenerRunResponse(
            as_of_date=date(2026, 3, 27),
            freshness_mode="computed",
            source_mode="pipeline",
            total_symbols=100,
            scanned_symbols=80,
            buy_candidates=[],
            watch_candidates=[],
            avoid_candidates=[],
            ready_to_buy_candidates=[],
            watch_pullback_candidates=[],
            watch_breakout_candidates=[],
            research_only_candidates=[],
        )

    def _build_step_output(output: ScreenerRunResponse) -> dict:
        return {
            "total_symbols": output.total_symbols,
            "scanned_symbols": output.scanned_symbols,
        }

    return WorkflowDefinition(
        name="screener_run",
        request_contract=ScreenerWorkflowRunRequest,
        final_output_contract=ScreenerRunResponse,
        nodes=(
            WorkflowNode(
                name="ScreenerRun",
                input_contract=ScreenerWorkflowRunRequest,
                output_contract=ScreenerRunResponse,
                handler=_run_screener,
                input_summary_builder=_build_step_input,
                output_summary_builder=_build_step_output,
            ),
        ),
        input_summary_builder=_build_input_summary,
        final_output_builder=lambda context: context.require_output(
            "ScreenerRun", ScreenerRunResponse
        ),
        final_output_summary_builder=_build_step_output,
    )
