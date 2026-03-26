"""Workflow runtime 核心对象定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from pydantic import BaseModel


@dataclass(frozen=True)
class WorkflowNode:
    """单个 workflow 节点定义。"""

    name: str
    input_contract: type[BaseModel]
    output_contract: type[BaseModel]
    handler: Callable[["WorkflowContext"], BaseModel]
    input_summary_builder: Callable[["WorkflowContext"], dict[str, Any]]
    output_summary_builder: Callable[[BaseModel], dict[str, Any]]


@dataclass(frozen=True)
class WorkflowDefinition:
    """Workflow 定义。"""

    name: str
    request_contract: type[BaseModel]
    final_output_contract: type[BaseModel]
    nodes: tuple[WorkflowNode, ...]
    input_summary_builder: Callable[[BaseModel], dict[str, Any]]
    final_output_builder: Callable[["WorkflowContext"], BaseModel]
    final_output_summary_builder: Callable[[BaseModel], dict[str, Any]]


@dataclass(frozen=True)
class WorkflowStepResult:
    """单个节点的执行结果。"""

    node_name: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass(frozen=True)
class WorkflowRunResult:
    """一次 workflow 执行结果。"""

    run_id: str
    workflow_name: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    input_summary: dict[str, Any] = field(default_factory=dict)
    steps: tuple[WorkflowStepResult, ...] = field(default_factory=tuple)
    final_output: Optional[BaseModel] = None
    final_output_summary: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass(frozen=True)
class WorkflowArtifact:
    """持久化后的 workflow 运行产物。"""

    run_id: str
    workflow_name: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    input_summary: dict[str, Any]
    steps: tuple[WorkflowStepResult, ...]
    final_output_summary: dict[str, Any]
    final_output: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None


class WorkflowExecutionError(RuntimeError):
    """workflow 节点执行失败。"""

    def __init__(self, workflow_name: str, node_name: str, message: str) -> None:
        self.workflow_name = workflow_name
        self.node_name = node_name
        self.message = message
        super().__init__(f"Workflow '{workflow_name}' node '{node_name}' failed: {message}")


from app.services.workflow_runtime.context import WorkflowContext  # noqa: E402
