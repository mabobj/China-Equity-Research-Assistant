"""Workflow runtime service facade."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
            }
        )

    def _to_run_response(self, result) -> WorkflowRunResponse:
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
