"""Workflow 运行上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class WorkflowContext:
    """Workflow 执行期间的共享上下文。"""

    run_id: str
    workflow_name: str
    request: BaseModel
    start_from: str | None = None
    stop_after: str | None = None
    use_llm: bool | None = None
    node_outputs: dict[str, BaseModel] = field(default_factory=dict)

    def set_output(self, node_name: str, output: BaseModel) -> None:
        """保存节点输出。"""
        self.node_outputs[node_name] = output

    def get_output(
        self,
        node_name: str,
        output_type: type[ModelT] | None = None,
    ) -> ModelT | BaseModel | None:
        """读取节点输出。"""
        output = self.node_outputs.get(node_name)
        if output is None:
            return None
        if output_type is not None and not isinstance(output, output_type):
            raise TypeError(
                f"节点 {node_name} 输出类型不匹配，期望 {output_type.__name__}，实际 {type(output).__name__}。"
            )
        return output

    def require_output(self, node_name: str, output_type: type[ModelT]) -> ModelT:
        """读取必须存在的节点输出。"""
        output = self.get_output(node_name, output_type)
        if output is None:
            raise KeyError(f"节点 {node_name} 输出不存在。")
        return output
