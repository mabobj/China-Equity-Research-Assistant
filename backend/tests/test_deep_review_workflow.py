"""Tests for deep candidate review workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.workflow import DeepReviewWorkflowRunRequest
from app.services.data_products.base import DataProductResult
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
            raise RuntimeError("mock review failure")
        return build_stock_review_report(symbol=symbol, name="Kweichow Moutai")


class StubDebateRuntimeService:
    def get_debate_review_report(self, symbol: str, use_llm: bool | None = None):
        return build_debate_review_report(
            symbol=symbol,
            name="Kweichow Moutai",
            runtime_mode="llm" if use_llm else "rule_based",
        )


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str):
        return build_strategy_plan(symbol=symbol, name="Kweichow Moutai")


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


def _build_definition(
    *,
    screener_pipeline=None,
    stock_review_service=None,
    debate_runtime_service=None,
    strategy_planner=None,
    review_report_daily=None,
    strategy_plan_daily=None,
    debate_review_daily=None,
):
    return build_deep_review_workflow_definition(
        screener_pipeline=screener_pipeline or StubScreenerPipeline(),
        stock_review_service=stock_review_service or StubStockReviewService(),
        debate_runtime_service=debate_runtime_service or StubDebateRuntimeService(),
        strategy_planner=strategy_planner or StubStrategyPlanner(),
        review_report_daily=review_report_daily or StubReviewReportDaily(),
        strategy_plan_daily=strategy_plan_daily or StubStrategyPlanDaily(),
        debate_review_daily=debate_review_daily or StubDebateReviewDaily(),
    )


def test_deep_review_workflow_records_symbol_failures(tmp_path: Path) -> None:
    definition = _build_definition()
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
    definition = _build_definition()
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


def test_deep_review_workflow_rejects_historical_recompute_request(
    tmp_path: Path,
) -> None:
    definition = _build_definition()
    executor = WorkflowExecutor(FileWorkflowArtifactStore(tmp_path))

    result = executor.execute(
        definition,
        DeepReviewWorkflowRunRequest(
            max_symbols=20,
            top_n=5,
            deep_top_k=2,
            as_of_date="2024-01-05",
            use_llm=False,
        ),
    )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "as_of_date" in result.error_message
