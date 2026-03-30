"""Workflow execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class WorkflowContext:
    """Shared context passed between workflow nodes."""

    run_id: str
    workflow_name: str
    request: BaseModel
    start_from: str | None = None
    stop_after: str | None = None
    use_llm: bool | None = None
    node_outputs: dict[str, BaseModel] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def set_output(self, node_name: str, output: BaseModel) -> None:
        self.node_outputs[node_name] = output

    def get_output(
        self,
        node_name: str,
        output_type: type[ModelT] | None = None,
    ) -> ModelT | BaseModel | None:
        output = self.node_outputs.get(node_name)
        if output is None:
            return None
        if output_type is not None and not isinstance(output, output_type):
            raise TypeError(
                f"Node '{node_name}' output type mismatch: expected "
                f"{output_type.__name__}, got {type(output).__name__}."
            )
        return output

    def require_output(self, node_name: str, output_type: type[ModelT]) -> ModelT:
        output = self.get_output(node_name, output_type)
        if output is None:
            raise KeyError(f"Node '{node_name}' output is missing.")
        return output

    def request_as(self, request_type: type[ModelT]) -> ModelT:
        if isinstance(self.request, request_type):
            return self.request
        return request_type.model_validate(self.request)

    def set_meta(self, key: str, value: object) -> None:
        self.metadata[key] = value

    def get_meta(self, key: str) -> object | None:
        return self.metadata.get(key)
