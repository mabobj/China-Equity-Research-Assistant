"""Workflow API tests."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_workflow_runtime_service
from app.main import app
from app.schemas.workflow import (
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowStepSummary,
)

client = TestClient(app)


class StubWorkflowRuntimeService:
    def __init__(self) -> None:
        self._detail_calls: dict[str, int] = {}
        self.last_single_stock_request = None

    def run_single_stock_workflow(self, request) -> WorkflowRunResponse:
        self.last_single_stock_request = request
        return WorkflowRunResponse(
            run_id="run-single",
            workflow_name="single_stock_full_review",
            status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            input_summary={"symbol": request.symbol},
            steps=[],
            final_output_summary={"symbol": request.symbol, "strategy_action": "WATCH"},
            error_message=None,
        )

    def run_deep_review_workflow(self, request) -> WorkflowRunResponse:
        return WorkflowRunResponse(
            run_id="run-deep",
            workflow_name="deep_candidate_review",
            status="running",
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            input_summary={"max_symbols": request.max_symbols},
            steps=[],
            final_output_summary={},
            error_message=None,
        )

    def run_screener_workflow(self, request) -> WorkflowRunResponse:
        return WorkflowRunResponse(
            run_id="run-screener",
            workflow_name="screener_run",
            status="running",
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            input_summary={"max_symbols": request.max_symbols, "top_n": request.top_n},
            steps=[],
            final_output_summary={},
            error_message=None,
        )

    def get_run_detail(self, run_id: str) -> WorkflowRunDetailResponse:
        count = self._detail_calls.get(run_id, 0) + 1
        self._detail_calls[run_id] = count

        if run_id == "run-screener" and count == 1:
            return WorkflowRunDetailResponse(
                run_id=run_id,
                workflow_name="screener_run",
                status="running",
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                input_summary={"max_symbols": 50, "top_n": 10},
                steps=[
                    WorkflowStepSummary(
                        node_name="ScreenerRun",
                        status="running",
                        message="Running screener pipeline",
                    )
                ],
                final_output_summary={},
                final_output=None,
                error_message=None,
            )

        if run_id == "run-screener":
            return WorkflowRunDetailResponse(
                run_id=run_id,
                workflow_name="screener_run",
                status="completed",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                input_summary={"max_symbols": 50, "top_n": 10},
                steps=[
                    WorkflowStepSummary(
                        node_name="ScreenerRun",
                        status="completed",
                        message="Completed screener pipeline",
                    )
                ],
                final_output_summary={"ready_to_buy_count": 2, "watch_count": 3},
                final_output=None,
                error_message=None,
            )

        if run_id == "run-deep" and count == 1:
            return WorkflowRunDetailResponse(
                run_id=run_id,
                workflow_name="deep_candidate_review",
                status="running",
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                input_summary={"max_symbols": 50},
                steps=[
                    WorkflowStepSummary(
                        node_name="CandidateReviewBuild",
                        status="running",
                        message="Building candidate reviews",
                    )
                ],
                final_output_summary={},
                final_output=None,
                error_message=None,
            )

        if run_id == "run-deep":
            return WorkflowRunDetailResponse(
                run_id=run_id,
                workflow_name="deep_candidate_review",
                status="completed",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                input_summary={"max_symbols": 50},
                steps=[
                    WorkflowStepSummary(
                        node_name="CandidateReviewBuild",
                        status="completed",
                        message="Completed with symbol failures",
                    )
                ],
                final_output_summary={
                    "success_count": 1,
                    "failure_count": 1,
                    "failed_symbols": ["000001.SZ"],
                },
                final_output=None,
                error_message=None,
                failed_symbols=["000001.SZ"],
                fallback_applied=True,
                fallback_reason="Some symbols failed and were skipped.",
                warning_messages=["Partial run with 1 failed symbol(s)."],
            )

        return WorkflowRunDetailResponse(
            run_id=run_id,
            workflow_name="single_stock_full_review",
            status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            input_summary={"symbol": "600519.SH"},
            steps=[],
            final_output_summary={"symbol": "600519.SH"},
            final_output=None,
            error_message=None,
        )


def test_run_single_stock_workflow_route_returns_structured_payload() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    response = client.post(
        "/workflows/single-stock/run",
        json={"symbol": "600519.SH", "use_llm": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_name"] == "single_stock_full_review"
    assert payload["final_output_summary"]["symbol"] == "600519.SH"

    app.dependency_overrides.clear()


def test_run_single_stock_workflow_route_passes_start_from_and_stop_after() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    response = client.post(
        "/workflows/single-stock/run",
        json={
            "symbol": "600519.SH",
            "start_from": "DebateReviewBuild",
            "stop_after": "DebateReviewBuild",
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    assert service.last_single_stock_request is not None
    assert service.last_single_stock_request.start_from == "DebateReviewBuild"
    assert service.last_single_stock_request.stop_after == "DebateReviewBuild"
    assert service.last_single_stock_request.use_llm is False

    app.dependency_overrides.clear()


def test_run_deep_review_workflow_route_returns_structured_payload() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    response = client.post(
        "/workflows/deep-review/run",
        json={"max_symbols": 50, "top_n": 10, "deep_top_k": 3, "use_llm": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_name"] == "deep_candidate_review"
    assert payload["status"] == "running"

    app.dependency_overrides.clear()


def test_run_screener_workflow_route_returns_running_payload() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    response = client.post(
        "/workflows/screener/run",
        json={"max_symbols": 50, "top_n": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_name"] == "screener_run"
    assert payload["status"] == "running"
    assert payload["run_id"] == "run-screener"

    app.dependency_overrides.clear()


def test_workflow_run_detail_route_supports_polling_chain_for_screener() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    start_response = client.post(
        "/workflows/screener/run",
        json={"max_symbols": 50, "top_n": 10},
    )
    run_id = start_response.json()["run_id"]

    first_poll = client.get(f"/workflows/runs/{run_id}")
    second_poll = client.get(f"/workflows/runs/{run_id}")

    assert first_poll.status_code == 200
    assert first_poll.json()["status"] == "running"
    assert first_poll.json()["steps"][0]["status"] == "running"

    assert second_poll.status_code == 200
    assert second_poll.json()["status"] == "completed"
    assert second_poll.json()["final_output_summary"]["ready_to_buy_count"] == 2

    app.dependency_overrides.clear()


def test_deep_review_workflow_polling_completes_with_symbol_failures() -> None:
    service = StubWorkflowRuntimeService()
    app.dependency_overrides[get_workflow_runtime_service] = lambda: service

    start_response = client.post(
        "/workflows/deep-review/run",
        json={"max_symbols": 50, "top_n": 10, "deep_top_k": 3},
    )
    run_id = start_response.json()["run_id"]

    first_poll = client.get(f"/workflows/runs/{run_id}")
    second_poll = client.get(f"/workflows/runs/{run_id}")

    assert first_poll.status_code == 200
    assert first_poll.json()["status"] == "running"

    assert second_poll.status_code == 200
    assert second_poll.json()["status"] == "completed"
    assert second_poll.json()["final_output_summary"]["failure_count"] == 1
    assert second_poll.json()["final_output_summary"]["success_count"] == 1
    assert second_poll.json()["failed_symbols"] == ["000001.SZ"]
    assert second_poll.json()["fallback_applied"] is True

    app.dependency_overrides.clear()
