"""Workflow runtime service facade."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import logging
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
    ScreenerWorkflowRunRequest,
    SingleStockWorkflowRunRequest,
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowStepSummary,
)
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import (
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowRunResult,
    WorkflowStepResult,
)
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry

logger = logging.getLogger(__name__)


class WorkflowRuntimeService:
    """Run workflows synchronously or start them in lightweight background threads."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor,
        artifact_store: FileWorkflowArtifactStore,
        background_executor: ThreadPoolExecutor | None = None,
        screener_batch_service: Any | None = None,
        stale_running_timeout_seconds: int = 60,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._artifact_store = artifact_store
        self._background_executor = background_executor or ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="workflow-runtime",
        )
        self._screener_batch_service = screener_batch_service
        self._stale_running_timeout = timedelta(
            seconds=max(stale_running_timeout_seconds, 30)
        )
        self._active_futures: dict[str, Future] = {}
        self._future_lock = Lock()

    def run_single_stock_workflow(
        self,
        request: SingleStockWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("single_stock_full_review")
        result = self._executor.execute(definition, request)
        return self._to_run_response(result)

    def run_deep_review_workflow(
        self,
        request: DeepReviewWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("deep_candidate_review")
        return self._start_background_workflow(definition, request)

    def run_screener_workflow(
        self,
        request: ScreenerWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("screener_run")
        running_artifact = self._find_valid_running_artifact(
            workflow_name=definition.name
        )
        if running_artifact is not None:
            return self._build_existing_running_response(running_artifact)

        def _on_started(artifact: WorkflowArtifact) -> None:
            if self._screener_batch_service is None:
                return
            batch_size = self._resolve_screener_batch_size(request)
            self._screener_batch_service.create_running_batch(
                run_id=artifact.run_id,
                batch_size=batch_size,
                max_symbols=request.max_symbols,
                top_n=request.top_n,
                started_at=artifact.started_at,
            )

        def _on_completed(result: WorkflowRunResult) -> None:
            if self._screener_batch_service is None:
                return
            final_output_dump = (
                result.final_output.model_dump(mode="json")
                if result.final_output is not None
                else None
            )
            self._screener_batch_service.finalize_batch(
                run_id=result.run_id,
                status=result.status,
                finished_at=result.finished_at,
                final_output=final_output_dump,
                final_output_summary=result.final_output_summary,
                error_message=result.error_message,
            )

        return self._start_background_workflow(
            definition,
            request,
            on_started=_on_started,
            on_completed=_on_completed,
        )

    def get_run_detail(self, run_id: str) -> WorkflowRunDetailResponse:
        artifact = self._artifact_store.load_run(run_id)
        visibility = self._build_runtime_visibility(
            workflow_name=artifact.workflow_name,
            input_summary=artifact.input_summary,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
        )
        return WorkflowRunDetailResponse.model_validate(
            {
                "run_id": artifact.run_id,
                "workflow_name": artifact.workflow_name,
                "status": artifact.status,
                "started_at": artifact.started_at,
                "finished_at": artifact.finished_at,
                "input_summary": artifact.input_summary,
                "steps": self._to_step_summaries(artifact.steps),
                "final_output_summary": artifact.final_output_summary,
                "final_output": artifact.final_output,
                "error_message": artifact.error_message,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def _start_background_workflow(
        self,
        definition: WorkflowDefinition,
        request,
        *,
        on_started: Callable[[WorkflowArtifact], None] | None = None,
        on_completed: Callable[[WorkflowRunResult], None] | None = None,
    ) -> WorkflowRunResponse:
        validated_request = definition.request_contract.model_validate(request)
        run_id = uuid4().hex
        started_at = datetime.now(timezone.utc)
        initial_artifact = WorkflowArtifact(
            run_id=run_id,
            workflow_name=definition.name,
            status="running",
            started_at=started_at,
            finished_at=None,
            input_summary=definition.input_summary_builder(validated_request),
            steps=tuple(),
            final_output_summary={},
            final_output=None,
            error_message=None,
        )
        self._artifact_store.save_artifact(initial_artifact)
        if on_started is not None:
            try:
                on_started(initial_artifact)
            except Exception:
                logger.exception(
                    "workflow.runtime.on_started_failed workflow=%s run_id=%s",
                    definition.name,
                    run_id,
                )
        future = self._background_executor.submit(
            self._run_background_workflow,
            definition,
            validated_request,
            run_id,
            started_at,
            on_completed,
        )
        with self._future_lock:
            self._active_futures[run_id] = future
        visibility = self._build_runtime_visibility(
            workflow_name=definition.name,
            input_summary=initial_artifact.input_summary,
            final_output_summary={},
            final_output=None,
        )
        return WorkflowRunResponse.model_validate(
            {
                "run_id": run_id,
                "workflow_name": definition.name,
                "status": "running",
                "started_at": started_at,
                "finished_at": None,
                "input_summary": initial_artifact.input_summary,
                "steps": [],
                "final_output_summary": {},
                "error_message": None,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def _run_background_workflow(
        self,
        definition: WorkflowDefinition,
        validated_request,
        run_id: str,
        started_at: datetime,
        on_completed: Callable[[WorkflowRunResult], None] | None,
    ) -> None:
        try:
            result = self._executor.execute(
                definition,
                validated_request,
                run_id=run_id,
                started_at=started_at,
                persist_initial_state=False,
            )
        except Exception:
            logger.exception(
                "workflow.runtime.background_failed workflow=%s run_id=%s",
                definition.name,
                run_id,
            )
            return
        finally:
            with self._future_lock:
                self._active_futures.pop(run_id, None)
        if on_completed is None:
            return
        try:
            on_completed(result)
        except Exception:
            logger.exception(
                "workflow.runtime.on_completed_failed workflow=%s run_id=%s",
                definition.name,
                run_id,
            )

    def _to_run_response(self, result) -> WorkflowRunResponse:
        final_output_dump = (
            result.final_output.model_dump(mode="json")
            if result.final_output is not None
            else None
        )
        visibility = self._build_runtime_visibility(
            workflow_name=result.workflow_name,
            input_summary=result.input_summary,
            final_output_summary=result.final_output_summary,
            final_output=final_output_dump,
        )
        return WorkflowRunResponse.model_validate(
            {
                "run_id": result.run_id,
                "workflow_name": result.workflow_name,
                "status": result.status,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "input_summary": result.input_summary,
                "steps": self._to_step_summaries(result.steps),
                "final_output_summary": result.final_output_summary,
                "error_message": result.error_message,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def _to_step_summaries(
        self,
        steps: tuple[WorkflowStepResult, ...],
    ) -> list[WorkflowStepSummary]:
        return [
            WorkflowStepSummary(
                node_name=step.node_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                message=step.message,
                input_summary=step.input_summary,
                output_summary=step.output_summary,
                error_message=step.error_message,
            )
            for step in steps
        ]

    def _build_runtime_visibility(
        self,
        *,
        workflow_name: str,
        input_summary: dict[str, Any],
        final_output_summary: dict[str, Any],
        final_output: dict[str, Any] | None,
    ) -> dict[str, Any]:
        requested_mode = self._requested_runtime_mode(input_summary=input_summary)
        debate_payload = self._extract_debate_payload(final_output=final_output)
        effective_mode = (
            debate_payload.get("runtime_mode_effective")
            or debate_payload.get("runtime_mode")
            or requested_mode
        )
        failed_symbols = self._extract_failed_symbols(
            final_output_summary=final_output_summary
        )
        fallback_applied = bool(debate_payload.get("fallback_applied")) or bool(
            failed_symbols
        )
        fallback_reason = debate_payload.get("fallback_reason")
        warning_messages = list(debate_payload.get("warning_messages") or [])
        summary_warnings = final_output_summary.get("warning_messages")
        if isinstance(summary_warnings, list):
            warning_messages.extend(
                str(item) for item in summary_warnings if isinstance(item, str)
            )

        if failed_symbols:
            if fallback_reason is None:
                fallback_reason = "Some symbols failed and were skipped."
            warning_messages.append(
                f"Partial run with {len(failed_symbols)} failed symbol(s)."
            )

        provider_used = debate_payload.get("provider_used") or "workflow_runtime"
        provider_candidates = debate_payload.get("provider_candidates") or [provider_used]

        return {
            "provider_used": provider_used,
            "provider_candidates": provider_candidates,
            "fallback_applied": fallback_applied,
            "fallback_reason": fallback_reason,
            "runtime_mode_requested": requested_mode,
            "runtime_mode_effective": effective_mode,
            "warning_messages": warning_messages,
            "failed_symbols": failed_symbols,
        }

    def _build_existing_running_response(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowRunResponse:
        visibility = self._build_runtime_visibility(
            workflow_name=artifact.workflow_name,
            input_summary=artifact.input_summary,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
        )
        warning_messages = list(visibility.get("warning_messages", []))
        warning_messages.append("已有运行中的初筛任务，本次请求复用现有运行记录。")
        visibility["warning_messages"] = warning_messages
        return WorkflowRunResponse.model_validate(
            {
                "run_id": artifact.run_id,
                "workflow_name": artifact.workflow_name,
                "status": artifact.status,
                "started_at": artifact.started_at,
                "finished_at": artifact.finished_at,
                "input_summary": artifact.input_summary,
                "steps": self._to_step_summaries(artifact.steps),
                "final_output_summary": artifact.final_output_summary,
                "error_message": artifact.error_message,
                "accepted": False,
                "existing_run_id": artifact.run_id,
                "message": "已有运行中的初筛任务，请等待当前任务完成。",
                **visibility,
            }
        )

    def _requested_runtime_mode(self, *, input_summary: dict[str, Any]) -> str | None:
        use_llm = input_summary.get("use_llm")
        if use_llm is None:
            return None
        return "llm" if bool(use_llm) else "rule_based"

    def _extract_debate_payload(self, *, final_output: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(final_output, dict):
            return {}
        debate_review = final_output.get("debate_review")
        if not isinstance(debate_review, dict):
            return {}
        return debate_review

    def _extract_failed_symbols(self, *, final_output_summary: dict[str, Any]) -> list[str]:
        raw = final_output_summary.get("failed_symbols")
        if not isinstance(raw, list):
            return []
        symbols: list[str] = []
        for item in raw:
            if isinstance(item, str) and item:
                symbols.append(item)
        return symbols

    def _find_valid_running_artifact(self, *, workflow_name: str) -> WorkflowArtifact | None:
        running = self._artifact_store.find_latest_run(
            workflow_name=workflow_name,
            status="running",
        )
        if running is None:
            return None

        with self._future_lock:
            future = self._active_futures.get(running.run_id)
            if future is not None and not future.done():
                return running
            if future is not None and future.done():
                self._active_futures.pop(running.run_id, None)

        now = datetime.now(timezone.utc)
        if now - running.started_at < self._stale_running_timeout:
            return running

        self._mark_stale_running_artifact_failed(running, finished_at=now)
        return None

    def _mark_stale_running_artifact_failed(
        self,
        artifact: WorkflowArtifact,
        *,
        finished_at: datetime,
    ) -> None:
        reason = "检测到陈旧的运行中记录，系统已自动标记为失败并允许重新发起任务。"
        failed_artifact = WorkflowArtifact(
            run_id=artifact.run_id,
            workflow_name=artifact.workflow_name,
            status="failed",
            started_at=artifact.started_at,
            finished_at=finished_at,
            input_summary=artifact.input_summary,
            steps=artifact.steps,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
            error_message=artifact.error_message or reason,
        )
        self._artifact_store.save_artifact(failed_artifact)
        if self._screener_batch_service is None:
            return
        self._screener_batch_service.finalize_batch(
            run_id=artifact.run_id,
            status="failed",
            finished_at=finished_at,
            final_output=artifact.final_output,
            final_output_summary=artifact.final_output_summary,
            error_message=reason,
        )

    def _resolve_screener_batch_size(self, request: ScreenerWorkflowRunRequest) -> int:
        if request.batch_size is not None:
            return request.batch_size
        if request.max_symbols is not None:
            return request.max_symbols
        return 50
