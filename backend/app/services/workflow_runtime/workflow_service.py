"""Workflow runtime service facade."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.screener import ScreenerRunResponse
from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
    ScreenerWorkflowRunRequest,
    SingleStockWorkflowRunRequest,
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowStepSummary,
)
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import WorkflowArtifact, WorkflowDefinition, WorkflowStepResult
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry


class WorkflowRuntimeService:
    """Run workflows synchronously or start them in lightweight background threads."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor,
        artifact_store: FileWorkflowArtifactStore,
        background_executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._artifact_store = artifact_store
        self._background_executor = background_executor or ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="workflow-runtime",
        )

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
        return self._start_background_workflow(definition, request)

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
                **visibility,
            }
        )

    def _start_background_workflow(
        self,
        definition: WorkflowDefinition,
        request,
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
        self._background_executor.submit(
            self._executor.execute,
            definition,
            validated_request,
            run_id=run_id,
            started_at=started_at,
            persist_initial_state=False,
        )
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
                **visibility,
            }
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
        failed_symbols = self._extract_failed_symbols(final_output_summary=final_output_summary)
        fallback_applied = bool(debate_payload.get("fallback_applied")) or bool(failed_symbols)
        fallback_reason = debate_payload.get("fallback_reason")
        warning_messages = list(debate_payload.get("warning_messages") or [])

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
