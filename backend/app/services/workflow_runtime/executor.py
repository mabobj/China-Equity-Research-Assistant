"""Synchronous workflow executor with artifact progress updates."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel

from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import (
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowExecutionError,
    WorkflowRunResult,
    WorkflowStepResult,
)
from app.services.workflow_runtime.context import WorkflowContext


class WorkflowExecutor:
    """Execute a workflow definition in process, node by node."""

    def __init__(self, artifact_store: FileWorkflowArtifactStore) -> None:
        self._artifact_store = artifact_store

    def execute(
        self,
        definition: WorkflowDefinition,
        request: BaseModel,
        *,
        run_id: str | None = None,
        started_at: datetime | None = None,
        persist_initial_state: bool = True,
    ) -> WorkflowRunResult:
        self._validate_definition(definition)
        validated_request = definition.request_contract.model_validate(request)
        start_index, stop_index = self._resolve_boundaries(
            definition=definition,
            start_from=getattr(validated_request, "start_from", None),
            stop_after=getattr(validated_request, "stop_after", None),
        )

        resolved_run_id = run_id or uuid4().hex
        resolved_started_at = started_at or datetime.now(timezone.utc)
        context = WorkflowContext(
            run_id=resolved_run_id,
            workflow_name=definition.name,
            request=validated_request,
            start_from=getattr(validated_request, "start_from", None),
            stop_after=getattr(validated_request, "stop_after", None),
            use_llm=getattr(validated_request, "use_llm", None),
        )
        input_summary = definition.input_summary_builder(validated_request)
        steps: list[WorkflowStepResult] = []
        status = "running"
        error_message: str | None = None

        if persist_initial_state:
            self._save_progress(
                run_id=resolved_run_id,
                workflow_name=definition.name,
                status=status,
                started_at=resolved_started_at,
                finished_at=None,
                input_summary=input_summary,
                steps=steps,
                final_output_summary={},
                final_output=None,
                error_message=None,
            )

        for index, node in enumerate(definition.nodes):
            if index < start_index:
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="skipped",
                        message="Skipped because the node is before start_from.",
                    )
                )
                self._save_running_state(
                    definition=definition,
                    run_id=resolved_run_id,
                    started_at=resolved_started_at,
                    input_summary=input_summary,
                    steps=steps,
                )
                continue

            if index > stop_index:
                steps.append(
                    WorkflowStepResult(
                        node_name=node.name,
                        status="skipped",
                        message="Skipped because the node is after stop_after.",
                    )
                )
                self._save_running_state(
                    definition=definition,
                    run_id=resolved_run_id,
                    started_at=resolved_started_at,
                    input_summary=input_summary,
                    steps=steps,
                )
                continue

            step_started_at = datetime.now(timezone.utc)
            input_step_summary = node.input_summary_builder(context)
            running_step = WorkflowStepResult(
                node_name=node.name,
                status="running",
                started_at=step_started_at,
                input_summary=input_step_summary,
                message=f"Running node '{node.name}'.",
            )
            steps.append(running_step)
            self._save_running_state(
                definition=definition,
                run_id=resolved_run_id,
                started_at=resolved_started_at,
                input_summary=input_summary,
                steps=steps,
            )

            try:
                raw_output = node.handler(context)
                output = self._validate_output(node.output_contract, raw_output)
                context.set_output(node.name, output)
                steps[-1] = WorkflowStepResult(
                    node_name=node.name,
                    status="completed",
                    started_at=step_started_at,
                    finished_at=datetime.now(timezone.utc),
                    input_summary=input_step_summary,
                    output_summary=node.output_summary_builder(output),
                )
                self._save_running_state(
                    definition=definition,
                    run_id=resolved_run_id,
                    started_at=resolved_started_at,
                    input_summary=input_summary,
                    steps=steps,
                )
            except Exception as exc:
                status = "failed"
                error_message = self._build_error_message(node.name, exc)
                steps[-1] = WorkflowStepResult(
                    node_name=node.name,
                    status="failed",
                    started_at=step_started_at,
                    finished_at=datetime.now(timezone.utc),
                    input_summary=input_step_summary,
                    error_message=error_message,
                )
                for remaining_node in definition.nodes[index + 1 :]:
                    steps.append(
                        WorkflowStepResult(
                            node_name=remaining_node.name,
                            status="skipped",
                            message="Skipped because a previous node failed.",
                        )
                    )
                break

        final_output = None
        final_output_summary: dict[str, object] = {}
        finished_at = datetime.now(timezone.utc)

        if status != "failed":
            status = "completed"
            final_output = self._validate_output(
                definition.final_output_contract,
                definition.final_output_builder(context),
            )
            final_output_summary = definition.final_output_summary_builder(final_output)

        result = WorkflowRunResult(
            run_id=resolved_run_id,
            workflow_name=definition.name,
            status=status,
            started_at=resolved_started_at,
            finished_at=finished_at,
            input_summary=input_summary,
            steps=tuple(steps),
            final_output=final_output,
            final_output_summary=final_output_summary,
            error_message=error_message,
        )
        self._artifact_store.save_run(result)
        return result

    def _save_running_state(
        self,
        *,
        definition: WorkflowDefinition,
        run_id: str,
        started_at: datetime,
        input_summary: dict[str, object],
        steps: list[WorkflowStepResult],
    ) -> None:
        self._save_progress(
            run_id=run_id,
            workflow_name=definition.name,
            status="running",
            started_at=started_at,
            finished_at=None,
            input_summary=input_summary,
            steps=steps,
            final_output_summary={},
            final_output=None,
            error_message=None,
        )

    def _save_progress(
        self,
        *,
        run_id: str,
        workflow_name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime | None,
        input_summary: dict[str, object],
        steps: list[WorkflowStepResult],
        final_output_summary: dict[str, object],
        final_output: dict[str, object] | None,
        error_message: str | None,
    ) -> None:
        self._artifact_store.save_artifact(
            WorkflowArtifact(
                run_id=run_id,
                workflow_name=workflow_name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                input_summary=input_summary,
                steps=tuple(steps),
                final_output_summary=final_output_summary,
                final_output=final_output,
                error_message=error_message,
            )
        )

    def _validate_definition(self, definition: WorkflowDefinition) -> None:
        node_names = [node.name for node in definition.nodes]
        if not node_names:
            raise ValueError(f"Workflow '{definition.name}' must contain at least one node.")
        if len(node_names) != len(set(node_names)):
            raise ValueError(f"Workflow '{definition.name}' contains duplicate node names.")

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
                raise ValueError(f"Unknown start_from node: '{start_from}'.")
            start_index = node_names.index(start_from)

        if stop_after is not None:
            if stop_after not in node_names:
                raise ValueError(f"Unknown stop_after node: '{stop_after}'.")
            stop_index = node_names.index(stop_after)

        if start_index > stop_index:
            raise ValueError("start_from cannot be after stop_after.")

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
        return f"Node '{node_name}' failed: {exc}"
