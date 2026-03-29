"""Tests for the single-stock workflow definition."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.workflow import SingleStockWorkflowRunRequest
from app.services.data_products.base import DataProductResult
from app.services.data_products.freshness import resolve_last_closed_trading_day
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


class StubReviewReportDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload):
        return DataProductResult(
            dataset="review_report_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class StubStrategyPlanDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload):
        return DataProductResult(
            dataset="strategy_plan_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class StubDebateReviewDaily:
    def load(self, symbol: str, *, as_of_date, variant: str = "rule_based"):
        return None

    def save(self, symbol: str, payload, *, variant: str = "rule_based"):
        return DataProductResult(
            dataset="debate_review_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class CachedReviewReportDaily(StubReviewReportDaily):
    def load(self, symbol: str, *, as_of_date):
        payload = build_stock_review_report(symbol=symbol).model_copy(
            update={"as_of_date": as_of_date}
        )
        return DataProductResult(
            dataset="review_report_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class CachedStrategyPlanDaily(StubStrategyPlanDaily):
    def load(self, symbol: str, *, as_of_date):
        payload = build_strategy_plan(symbol=symbol).model_copy(
            update={"as_of_date": as_of_date}
        )
        return DataProductResult(
            dataset="strategy_plan_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class CachedDebateReviewDaily(StubDebateReviewDaily):
    def load(self, symbol: str, *, as_of_date, variant: str = "rule_based"):
        payload = build_debate_review_report(
            symbol=symbol,
            runtime_mode="llm" if variant == "llm" else "rule_based",
        ).model_copy(
            update={
                "as_of_date": as_of_date,
                "runtime_mode_requested": "llm" if variant == "llm" else "rule_based",
                "runtime_mode_effective": "llm" if variant == "llm" else "rule_based",
            }
        )
        return DataProductResult(
            dataset="debate_review_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


class FailingStockReviewService:
    def get_stock_review_report(self, symbol: str):
        raise RuntimeError("review should not be recomputed")


class FailingStrategyPlanner:
    def get_strategy_plan(self, symbol: str):
        raise RuntimeError("strategy should not be recomputed")


class FailingDebateRuntimeService(StubDebateRuntimeService):
    def get_debate_review_report(self, symbol: str, use_llm: bool | None = None):
        raise RuntimeError("debate should not be recomputed")


def _build_definition(
    *,
    debate_orchestrator=None,
    factor_snapshot_service=None,
    stock_review_service=None,
    debate_runtime_service=None,
    strategy_planner=None,
    review_report_daily=None,
    strategy_plan_daily=None,
    debate_review_daily=None,
):
    return build_single_stock_workflow_definition(
        debate_orchestrator=debate_orchestrator or StubDebateOrchestrator(),
        factor_snapshot_service=factor_snapshot_service or StubFactorSnapshotService(),
        stock_review_service=stock_review_service or StubStockReviewService(),
        debate_runtime_service=debate_runtime_service or StubDebateRuntimeService(),
        strategy_planner=strategy_planner or StubStrategyPlanner(),
        review_report_daily=review_report_daily or StubReviewReportDaily(),
        strategy_plan_daily=strategy_plan_daily or StubStrategyPlanDaily(),
        debate_review_daily=debate_review_daily or StubDebateReviewDaily(),
    )


def test_single_stock_workflow_runs_successfully(tmp_path: Path) -> None:
    debate_runtime_service = StubDebateRuntimeService()
    definition = _build_definition(debate_runtime_service=debate_runtime_service)
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
    debate_runtime_service = StubDebateRuntimeService()
    definition = _build_definition(debate_runtime_service=debate_runtime_service)
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
    definition = _build_definition()
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


def test_single_stock_workflow_prefers_review_debate_strategy_snapshots(
    tmp_path: Path,
) -> None:
    definition = _build_definition(
        stock_review_service=FailingStockReviewService(),
        debate_runtime_service=FailingDebateRuntimeService(),
        strategy_planner=FailingStrategyPlanner(),
        review_report_daily=CachedReviewReportDaily(),
        strategy_plan_daily=CachedStrategyPlanDaily(),
        debate_review_daily=CachedDebateReviewDaily(),
    )
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        SingleStockWorkflowRunRequest(symbol="600519.SH", use_llm=False),
    )

    assert result.status == "completed"
    assert result.final_output is not None
    assert result.final_output.review_report is not None
    assert result.final_output.strategy_plan is not None
    assert result.final_output.debate_review is not None
    assert result.final_output.review_report.freshness_mode == "cache_hit"
    assert result.final_output.strategy_plan.freshness_mode == "cache_hit"
    assert result.final_output.debate_review.freshness_mode == "cache_hit"
    assert result.final_output.review_report.as_of_date == resolve_last_closed_trading_day()
