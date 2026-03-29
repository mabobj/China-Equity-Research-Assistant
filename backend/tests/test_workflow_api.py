"""Workflow API 测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_workflow_runtime_service
from app.main import app
from app.schemas.workflow import WorkflowRunDetailResponse, WorkflowRunResponse

client = TestClient(app)


class StubWorkflowRuntimeService:
    def run_single_stock_workflow(self, request) -> WorkflowRunResponse:
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
    """单票 workflow 路由应返回结构化响应。"""
    app.dependency_overrides[get_workflow_runtime_service] = (
        lambda: StubWorkflowRuntimeService()
    )

    response = client.post(
        "/workflows/single-stock/run",
        json={"symbol": "600519.SH", "use_llm": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_name"] == "single_stock_full_review"
    assert payload["final_output_summary"]["symbol"] == "600519.SH"

    app.dependency_overrides.clear()


def test_run_deep_review_workflow_route_returns_structured_payload() -> None:
    """深筛 workflow 路由应返回结构化响应。"""
    app.dependency_overrides[get_workflow_runtime_service] = (
        lambda: StubWorkflowRuntimeService()
    )

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
    """Screener workflow should return a run id immediately for polling."""
    app.dependency_overrides[get_workflow_runtime_service] = (
        lambda: StubWorkflowRuntimeService()
    )

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


def test_get_workflow_run_detail_route_returns_structured_payload() -> None:
    """运行详情路由应返回步骤与摘要。"""
    app.dependency_overrides[get_workflow_runtime_service] = (
        lambda: StubWorkflowRuntimeService()
    )

    response = client.get("/workflows/runs/run-single")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-single"
    assert payload["workflow_name"] == "single_stock_full_review"
    assert payload["input_summary"]["symbol"] == "600519.SH"

    app.dependency_overrides.clear()
