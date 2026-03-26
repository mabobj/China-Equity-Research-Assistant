"""深筛 workflow 测试。"""

from __future__ import annotations

from pathlib import Path

from app.schemas.workflow import DeepReviewWorkflowRunRequest
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.definitions.deep_review_workflow import (
    build_deep_review_workflow_definition,
)
from app.services.workflow_runtime.executor import WorkflowExecutor
from .workflow_test_helpers import (
    build_debate_review_report,
    build_screener_run_response,
    build_stock_review_report,
    build_strategy_plan,
)


class StubScreenerPipeline:
    def run_screener(self, max_symbols: int | None = None, top_n: int | None = None):
        return build_screener_run_response()


class StubStockReviewService:
    def get_stock_review_report(self, symbol: str):
        if symbol == "000001.SZ":
            raise RuntimeError("模拟 review 失败")
        return build_stock_review_report(symbol=symbol, name="贵州茅台")


class StubDebateRuntimeService:
    def get_debate_review_report(self, symbol: str, use_llm: bool | None = None):
        return build_debate_review_report(
            symbol=symbol,
            name="贵州茅台",
            runtime_mode="llm" if use_llm else "rule_based",
        )


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str):
        return build_strategy_plan(symbol=symbol, name="贵州茅台")


def test_deep_review_workflow_records_symbol_failures(tmp_path: Path) -> None:
    """深筛 workflow 应允许个别标的失败并记录摘要。"""
    definition = build_deep_review_workflow_definition(
        screener_pipeline=StubScreenerPipeline(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=StubDebateRuntimeService(),
        strategy_planner=StubStrategyPlanner(),
    )
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        DeepReviewWorkflowRunRequest(max_symbols=20, top_n=5, deep_top_k=2, use_llm=True),
    )

    assert result.status == "completed"
    assert result.final_output is not None
    assert len(result.final_output.candidates) == 1
    assert result.final_output.candidates[0].symbol == "600519.SH"
    assert len(result.final_output.failures) == 1
    assert result.final_output.failures[0].symbol == "000001.SZ"
    assert result.final_output.candidates[0].debate_review is not None
    assert result.final_output.candidates[0].strategy_plan is not None


def test_deep_review_workflow_can_start_from_candidate_debate(tmp_path: Path) -> None:
    """深筛 workflow 从中间节点启动时应自动补齐前置输入。"""
    definition = build_deep_review_workflow_definition(
        screener_pipeline=StubScreenerPipeline(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=StubDebateRuntimeService(),
        strategy_planner=StubStrategyPlanner(),
    )
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        DeepReviewWorkflowRunRequest(
            max_symbols=20,
            top_n=5,
            deep_top_k=2,
            start_from="CandidateDebateBuild",
            stop_after="CandidateStrategyBuild",
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
    assert result.final_output.screener_run is not None
    assert result.final_output.candidate_selection is not None
    assert len(result.final_output.candidates) == 1
    assert len(result.final_output.failures) == 1
