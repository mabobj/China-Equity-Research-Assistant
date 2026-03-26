"""单票 workflow 测试。"""

from __future__ import annotations

from pathlib import Path

from app.schemas.workflow import SingleStockWorkflowRunRequest
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.definitions.single_stock_workflow import (
    build_single_stock_workflow_definition,
)
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry
from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService
from .workflow_test_helpers import (
    build_debate_review_report,
    build_factor_snapshot,
    build_single_stock_research_inputs,
    build_stock_review_report,
    build_strategy_plan,
)


class StubDebateOrchestrator:
    def build_inputs(self, symbol: str):
        return build_single_stock_research_inputs(symbol=symbol)


class StubFactorSnapshotService:
    def get_factor_snapshot(self, symbol: str):
        return build_factor_snapshot(symbol=symbol)


class StubStockReviewService:
    def get_stock_review_report(self, symbol: str):
        return build_stock_review_report(symbol=symbol)


class StubDebateRuntimeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool | None]] = []

    def get_debate_review_report(self, symbol: str, use_llm: bool | None = None):
        self.calls.append((symbol, use_llm))
        return build_debate_review_report(
            symbol=symbol,
            runtime_mode="llm" if use_llm else "rule_based",
        )


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str):
        return build_strategy_plan(symbol=symbol)


def test_single_stock_workflow_runs_successfully(tmp_path: Path) -> None:
    """单票 workflow 应按节点顺序完成并保留统一输出。"""
    debate_runtime_service = StubDebateRuntimeService()
    definition = build_single_stock_workflow_definition(
        debate_orchestrator=StubDebateOrchestrator(),
        factor_snapshot_service=StubFactorSnapshotService(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=debate_runtime_service,
        strategy_planner=StubStrategyPlanner(),
    )
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        SingleStockWorkflowRunRequest(symbol="600519.SH", use_llm=True),
    )

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.symbol == "600519.SH"
    assert result.final_output.review_report is not None
    assert result.final_output.debate_review is not None
    assert result.final_output.debate_review.runtime_mode == "llm"
    assert result.final_output.strategy_plan is not None
    assert debate_runtime_service.calls == [("600519.SH", True)]
    assert [step.node_name for step in result.steps] == [
        "SingleStockResearchInputs",
        "FactorSnapshotBuild",
        "ReviewReportBuild",
        "DebateReviewBuild",
        "StrategyPlanBuild",
    ]


def test_single_stock_workflow_can_start_from_middle_node(tmp_path: Path) -> None:
    """单票 workflow 应支持从中间节点启动。"""
    debate_runtime_service = StubDebateRuntimeService()
    definition = build_single_stock_workflow_definition(
        debate_orchestrator=StubDebateOrchestrator(),
        factor_snapshot_service=StubFactorSnapshotService(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=debate_runtime_service,
        strategy_planner=StubStrategyPlanner(),
    )
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        SingleStockWorkflowRunRequest(
            symbol="600519.SH",
            start_from="DebateReviewBuild",
            stop_after="StrategyPlanBuild",
            use_llm=False,
        ),
    )

    assert result.status == "completed"
    assert [step.status for step in result.steps] == [
        "skipped",
        "skipped",
        "skipped",
        "completed",
        "completed",
    ]
    assert result.final_output is not None
    assert result.final_output.research_inputs is None
    assert result.final_output.factor_snapshot is None
    assert result.final_output.review_report is None
    assert result.final_output.debate_review is not None
    assert result.final_output.strategy_plan is not None
    assert debate_runtime_service.calls == [("600519.SH", False)]


def test_workflow_runtime_service_serializes_step_summaries(tmp_path: Path) -> None:
    """workflow runtime service 应把内部步骤结果转换为对外 schema。"""
    definition = build_single_stock_workflow_definition(
        debate_orchestrator=StubDebateOrchestrator(),
        factor_snapshot_service=StubFactorSnapshotService(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=StubDebateRuntimeService(),
        strategy_planner=StubStrategyPlanner(),
    )
    artifact_store = FileWorkflowArtifactStore(tmp_path)
    service = WorkflowRuntimeService(
        registry=WorkflowRegistry(definitions=(definition,)),
        executor=WorkflowExecutor(artifact_store),
        artifact_store=artifact_store,
    )

    response = service.run_single_stock_workflow(
        SingleStockWorkflowRunRequest(symbol="600519.SH", use_llm=False)
    )
    detail = service.get_run_detail(response.run_id)

    assert response.status == "completed"
    assert len(response.steps) == 5
    assert response.steps[0].node_name == "SingleStockResearchInputs"
    assert detail.steps[0].node_name == "SingleStockResearchInputs"
