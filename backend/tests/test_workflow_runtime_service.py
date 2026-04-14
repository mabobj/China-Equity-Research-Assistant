"""Workflow runtime 可见性与长任务状态测试。"""

from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas.evaluation import ModelEvaluationResponse, ModelVersionRecommendation
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import WorkflowArtifact, WorkflowStepResult
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry
from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService


class _StubEvaluationService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_model_evaluation(self, model_version: str) -> ModelEvaluationResponse:
        self.calls.append(model_version)
        return ModelEvaluationResponse(
            model_version=model_version,
            feature_version="features-v0-baseline",
            label_version="labels-v0-forward-return",
            evaluated_at=datetime.now(timezone.utc),
            window_start=datetime(2026, 3, 1, tzinfo=timezone.utc).date(),
            window_end=datetime(2026, 3, 30, tzinfo=timezone.utc).date(),
            metrics={"quality_score": 0.62},
            strengths=["回测稳定性可接受。"],
            risks=["样本仍需继续积累。"],
            warning_messages=[],
            backtest_references=[],
            comparison=None,
            recommendation=ModelVersionRecommendation(
                recommendation="promote_candidate",
                recommended_model_version="candidate-v2",
                reason="候选版本胜率与收益均有改善。",
                supporting_metrics={"win_rate_delta": 0.03},
                guardrails=["保持质量门控。"],
            ),
        )


class _StubExperimentService:
    def get_default_model_version(self) -> str:
        return "baseline-rule-v1"


def _build_service(tmp_path: Path) -> WorkflowRuntimeService:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts")
    executor = WorkflowExecutor(artifact_store=artifact_store)
    evaluation_service = _StubEvaluationService()
    return WorkflowRuntimeService(
        registry=WorkflowRegistry(definitions=()),
        executor=executor,
        artifact_store=artifact_store,
        evaluation_service=evaluation_service,
        experiment_service=_StubExperimentService(),
        stale_running_timeout_seconds=60,
    )


def test_runtime_visibility_includes_model_recommendation_and_alert(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    service._recommendation_cache["candidate-v2"] = (  # noqa: SLF001
        datetime.now(timezone.utc),
        ModelVersionRecommendation(
            recommendation="promote_candidate",
            recommended_model_version="candidate-v2",
            reason="cached recommendation",
            supporting_metrics={"win_rate_delta": 0.03},
            guardrails=["keep quality gate"],
        ).model_dump(mode="json"),
    )

    visibility = service._build_runtime_visibility(  # noqa: SLF001
        status="completed",
        workflow_name="screener_run",
        input_summary={},
        final_output_summary={},
        final_output={
            "ready_to_buy_candidates": [
                {"symbol": "600519.SH", "predictive_model_version": "candidate-v2"}
            ]
        },
    )

    recommendation = visibility["model_recommendation"]
    assert recommendation is not None
    assert recommendation["recommended_model_version"] == "candidate-v2"
    assert visibility["version_recommendation_alert"] is not None
    assert "baseline-rule-v1" in visibility["version_recommendation_alert"]
    assert service._evaluation_service.calls == []  # noqa: SLF001


def test_runtime_visibility_without_predictive_version_has_no_recommendation(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    visibility = service._build_runtime_visibility(  # noqa: SLF001
        status="completed",
        workflow_name="single_stock_full_review",
        input_summary={},
        final_output_summary={},
        final_output={"symbol": "600519.SH"},
    )

    assert visibility["model_recommendation"] is None
    assert visibility["version_recommendation_alert"] is None


def test_runtime_visibility_does_not_resolve_model_recommendation_while_running(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    visibility = service._build_runtime_visibility(  # noqa: SLF001
        status="running",
        workflow_name="screener_run",
        input_summary={},
        final_output_summary={},
        final_output={
            "ready_to_buy_candidates": [
                {"symbol": "600519.SH", "predictive_model_version": "candidate-v2"}
            ]
        },
    )

    assert visibility["model_recommendation"] is None
    assert visibility["version_recommendation_alert"] is None
    assert service._evaluation_service.calls == []  # noqa: SLF001


def test_get_run_detail_keeps_running_artifact_when_future_is_active(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    stale_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    run_id = "stale-running-run"
    service._artifact_store.save_artifact(  # noqa: SLF001
        WorkflowArtifact(
            run_id=run_id,
            workflow_name="screener_run",
            status="running",
            started_at=stale_started_at,
            finished_at=None,
            input_summary={},
            steps=(
                WorkflowStepResult(
                    node_name="ScreenerRun",
                    status="running",
                    started_at=stale_started_at,
                    message="Running node 'ScreenerRun'.",
                ),
            ),
            final_output_summary={},
            final_output=None,
            error_message=None,
        )
    )
    service._active_futures[run_id] = Future()  # noqa: SLF001

    detail = service.get_run_detail(run_id)

    assert detail.status == "running"
    assert detail.error_message is None
    assert service._evaluation_service.calls == []  # noqa: SLF001


def test_get_run_detail_marks_stale_running_artifact_failed_without_future(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    stale_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    run_id = "stale-running-no-future"
    service._artifact_store.save_artifact(  # noqa: SLF001
        WorkflowArtifact(
            run_id=run_id,
            workflow_name="screener_run",
            status="running",
            started_at=stale_started_at,
            finished_at=None,
            input_summary={},
            steps=(
                WorkflowStepResult(
                    node_name="ScreenerRun",
                    status="running",
                    started_at=stale_started_at,
                    message="Running node 'ScreenerRun'.",
                ),
            ),
            final_output_summary={},
            final_output=None,
            error_message=None,
        )
    )

    detail = service.get_run_detail(run_id)

    assert detail.status == "failed"
    assert detail.error_message is not None
    assert "自动标记为失败" in detail.error_message
