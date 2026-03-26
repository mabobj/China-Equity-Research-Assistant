"""同步 workflow 执行器。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel

from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import (
    WorkflowDefinition,
    WorkflowExecutionError,
    WorkflowRunResult,
    WorkflowStepResult,
)
from app.services.workflow_runtime.context import WorkflowContext


class WorkflowExecutor:
    """按顺序同步执行 workflow。"""

    def __init__(self, artifact_store: FileWorkflowArtifactStore) -> None:
        self._artifact_store = artifact_store

    def execute(
        self,
        definition: WorkflowDefinition,
        request: BaseModel,
    ) -> WorkflowRunResult:
        """执行指定 workflow。"""
        self._validate_definition(definition)
        validated_request = definition.request_contract.model_validate(request)
        start_index, stop_index = self._resolve_boundaries(
            definition=definition,
            start_from=getattr(validated_request, "start_from", None),
            stop_after=getattr(validated_request, "stop_after", None),
        )

        run_id = uuid4().hex
        started_at = datetime.now(timezone.utc)
        context = WorkflowContext(
            run_id=run_id,
            workflow_name=definition.name,
            request=validated_request,
            start_from=getattr(validated_request, "start_from", None),
            stop_after=getattr(validated_request, "stop_after", None),
            use_llm=getattr(validated_request, "use_llm", None),
        )
        steps: list[WorkflowStepResult] = []
        status = "completed"
        error_message: str | None = None

        for index, node in enumerate(definition.nodes):
            if index < start_index:
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="skipped",
                        message="该节点位于 start_from 之前，已跳过。",
                    )
                )
                continue

            if index > stop_index:
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="skipped",
                        message="该节点位于 stop_after 之后，未执行。",
                    )
                )
                continue

            step_started_at = datetime.now(timezone.utc)
            input_summary = node.input_summary_builder(context)
            try:
                raw_output = node.handler(context)
                output = self._validate_output(node.output_contract, raw_output)
                context.set_output(node.name, output)
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="completed",
                        started_at=step_started_at,
                        finished_at=datetime.now(timezone.utc),
                        input_summary=input_summary,
                        output_summary=node.output_summary_builder(output),
                    )
                )
            except Exception as exc:
                status = "failed"
                error_message = self._build_error_message(node.name, exc)
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="failed",
                        started_at=step_started_at,
                        finished_at=datetime.now(timezone.utc),
                        input_summary=input_summary,
                        error_message=error_message,
                    )
                )
                for remaining_node in definition.nodes[index + 1 :]:
                    steps.append(
                        WorkflowStepResult(
                            node_name=remaining_node.name,
                            status="skipped",
                            message="前置节点失败，后续节点未执行。",
                        )
                    )
                break

        final_output = None
        final_output_summary: dict[str, object] = {}
        if status == "completed":
            final_output = self._validate_output(
                definition.final_output_contract,
                definition.final_output_builder(context),
            )
            final_output_summary = definition.final_output_summary_builder(final_output)

        finished_at = datetime.now(timezone.utc)
        result = WorkflowRunResult(
            run_id=run_id,
            workflow_name=definition.name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            input_summary=definition.input_summary_builder(validated_request),
            steps=tuple(steps),
            final_output=final_output,
            final_output_summary=final_output_summary,
            error_message=error_message,
        )
        self._artifact_store.save_run(result)
        return result

    def _validate_definition(self, definition: WorkflowDefinition) -> None:
        node_names = [node.name for node in definition.nodes]
        if not node_names:
            raise ValueError(f"Workflow '{definition.name}' 至少需要一个节点。")
        if len(node_names) != len(set(node_names)):
            raise ValueError(f"Workflow '{definition.name}' 的节点名称不能重复。")

    def _resolve_boundaries(
        self,
        *,
        definition: WorkflowDefinition,
        start_from: str | None,
        stop_after: str | None,
    ) -> tuple[int, int]:
        node_names = [node.name for node in definition.nodes]
        start_index = 0
        stop_index = len(node_names) - 1

        if start_from is not None:
            if start_from not in node_names:
                raise ValueError(f"start_from 节点 '{start_from}' 不存在。")
            start_index = node_names.index(start_from)

        if stop_after is not None:
            if stop_after not in node_names:
                raise ValueError(f"stop_after 节点 '{stop_after}' 不存在。")
            stop_index = node_names.index(stop_after)

        if start_index > stop_index:
            raise ValueError("start_from 不能位于 stop_after 之后。")

        return start_index, stop_index

    def _validate_output(
        self,
        output_contract: type[BaseModel],
        raw_output: BaseModel,
    ) -> BaseModel:
        if isinstance(raw_output, output_contract):
            return raw_output
        return output_contract.model_validate(raw_output)

    def _build_error_message(self, node_name: str, exc: Exception) -> str:
        if isinstance(exc, WorkflowExecutionError):
            return exc.message
        return f"节点 {node_name} 执行失败：{exc}"
