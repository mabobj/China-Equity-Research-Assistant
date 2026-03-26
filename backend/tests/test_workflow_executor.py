"""Workflow 执行器测试。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import WorkflowDefinition, WorkflowNode
from app.services.workflow_runtime.context import WorkflowContext
from app.services.workflow_runtime.executor import WorkflowExecutor


class FakeWorkflowRequest(BaseModel):
    start_from: str | None = None
    stop_after: str | None = None
    use_llm: bool | None = None


class FakeNodeOutput(BaseModel):
    value: int


class FakeWorkflowOutput(BaseModel):
    last_value: int | None = None


def _build_fake_definition(should_fail: bool = False) -> WorkflowDefinition:
    def build_node_output(value: int) -> FakeNodeOutput:
        return FakeNodeOutput(value=value)

    def handle_first(context: WorkflowContext) -> FakeNodeOutput:
        return build_node_output(1)

    def handle_second(context: WorkflowContext) -> FakeNodeOutput:
        if should_fail:
            raise RuntimeError("boom")
        return build_node_output(2)

    def handle_third(context: WorkflowContext) -> FakeNodeOutput:
        return build_node_output(3)

    def build_input_summary(context: WorkflowContext) -> dict[str, int]:
        return {"has_outputs": len(context.node_outputs)}

    def build_output_summary(output: FakeNodeOutput) -> dict[str, int]:
        return {"value": output.value}

    def build_final_output(context: WorkflowContext) -> FakeWorkflowOutput:
        for node_name in ("NodeC", "NodeB", "NodeA"):
            output = context.get_output(node_name, FakeNodeOutput)
            if output is not None:
                return FakeWorkflowOutput(last_value=output.value)
        return FakeWorkflowOutput(last_value=None)

    return WorkflowDefinition(
        name="fake_workflow",
        request_contract=FakeWorkflowRequest,
        final_output_contract=FakeWorkflowOutput,
        nodes=(
            WorkflowNode(
                name="NodeA",
                input_contract=FakeWorkflowRequest,
                output_contract=FakeNodeOutput,
                handler=handle_first,
                input_summary_builder=build_input_summary,
                output_summary_builder=build_output_summary,
            ),
            WorkflowNode(
                name="NodeB",
                input_contract=FakeNodeOutput,
                output_contract=FakeNodeOutput,
                handler=handle_second,
                input_summary_builder=build_input_summary,
                output_summary_builder=build_output_summary,
            ),
            WorkflowNode(
                name="NodeC",
                input_contract=FakeNodeOutput,
                output_contract=FakeNodeOutput,
                handler=handle_third,
                input_summary_builder=build_input_summary,
                output_summary_builder=build_output_summary,
            ),
        ),
        input_summary_builder=lambda request: {
            "start_from": request.start_from,
            "stop_after": request.stop_after,
        },
        final_output_builder=build_final_output,
        final_output_summary_builder=lambda output: {"last_value": output.last_value},
    )


def test_workflow_executor_supports_start_from_and_stop_after(tmp_path: Path) -> None:
    """执行器应支持从中间节点启动并在指定节点后停止。"""
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))
    definition = _build_fake_definition()

    result = executor.execute(
        definition,
        FakeWorkflowRequest(start_from="NodeB", stop_after="NodeC"),
    )

    assert result.status == "completed"
    assert [step.status for step in result.steps] == ["skipped", "completed", "completed"]
    assert result.final_output is not None
    assert result.final_output.last_value == 3


def test_workflow_executor_returns_failed_status_and_persists_artifact(
    tmp_path: Path,
) -> None:
    """节点失败时应返回失败状态并保留运行记录。"""
    artifact_store = FileWorkflowArtifactStore(tmp_path)
    executor = WorkflowExecutor(artifact_store)
    definition = _build_fake_definition(should_fail=True)

    result = executor.execute(definition, FakeWorkflowRequest())
    artifact = artifact_store.load_run(result.run_id)

    assert result.status == "failed"
    assert result.error_message is not None
    assert artifact.status == "failed"
    assert artifact.steps[1].status == "failed"
    assert artifact.steps[2].status == "skipped"


def test_workflow_executor_rejects_invalid_boundaries(tmp_path: Path) -> None:
    """非法 start_from 与 stop_after 组合应返回清晰错误。"""
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))
    definition = _build_fake_definition()

    try:
        executor.execute(
            definition,
            FakeWorkflowRequest(start_from="NodeC", stop_after="NodeA"),
        )
    except ValueError as exc:
        assert "start_from" in str(exc)
    else:
        raise AssertionError("应当抛出 ValueError。")
