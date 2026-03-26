"""Workflow runtime 服务门面。"""

from __future__ import annotations

from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowStepSummary,
    SingleStockWorkflowRunRequest,
)
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import WorkflowStepResult
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry


class WorkflowRuntimeService:
    """统一封装 workflow 执行与运行记录查询。"""

    def __init__(
        self,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor,
        artifact_store: FileWorkflowArtifactStore,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._artifact_store = artifact_store

    def run_single_stock_workflow(
        self,
        request: SingleStockWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        """运行单票完整研判 workflow。"""
        definition = self._registry.get_definition("single_stock_full_review")
        result = self._executor.execute(definition, request)
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

    def run_deep_review_workflow(
        self,
        request: DeepReviewWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        """运行深筛复核 workflow。"""
        definition = self._registry.get_definition("deep_candidate_review")
        result = self._executor.execute(definition, request)
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

    def get_run_detail(self, run_id: str) -> WorkflowRunDetailResponse:
        """读取 workflow 运行详情。"""
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

    def _to_step_summaries(
        self,
        steps: tuple[WorkflowStepResult, ...],
    ) -> list[WorkflowStepSummary]:
        """把内部步骤结果转换为 API schema。"""
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
