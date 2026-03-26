"""Workflow 定义注册表。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.workflow_runtime.base import WorkflowDefinition


@dataclass(frozen=True)
class WorkflowRegistry:
    """维护 workflow 定义的名称索引。"""

    definitions: tuple[WorkflowDefinition, ...]

    def __post_init__(self) -> None:
        names = [definition.name for definition in self.definitions]
        if len(names) != len(set(names)):
            raise ValueError("Workflow definition 名称不能重复。")

    def get_definition(self, workflow_name: str) -> WorkflowDefinition:
        """按名称读取 workflow 定义。"""
        for definition in self.definitions:
            if definition.name == workflow_name:
                return definition
        raise KeyError(f"Workflow '{workflow_name}' 未注册。")
