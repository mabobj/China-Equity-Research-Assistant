"""API tests for screener scheme routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from datetime import datetime, timezone

from app.api.dependencies import (
    get_screener_scheme_review_service,
    get_screener_scheme_service,
)
from app.main import app
from app.schemas.screener_scheme_review import (
    ScreenerSchemeFeedbackSummary,
    ScreenerSchemeReviewStatsResponse,
    ScreenerSchemeRunSummary,
    ScreenerSchemeRunsResponse,
    ScreenerSchemeStats,
    ScreenerSchemeStatsResponse,
)
from app.services.screener_service.scheme_service import ScreenerSchemeService

client = TestClient(app)


def test_list_schemes_route_returns_builtin_default(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    app.dependency_overrides[get_screener_scheme_service] = lambda: service

    response = client.get("/screener/schemes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["scheme_id"] == "default_builtin_scheme"
    assert payload["items"][0]["current_version"] == "legacy_v1"

    app.dependency_overrides.clear()


def test_create_scheme_and_version_routes_work_together(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    app.dependency_overrides[get_screener_scheme_service] = lambda: service

    create_scheme = client.post(
        "/screener/schemes",
        json={
            "name": "质量优先方案",
            "description": "用于 API 测试",
            "is_default": False,
        },
    )
    assert create_scheme.status_code == 200
    scheme_id = create_scheme.json()["scheme"]["scheme_id"]

    create_version = client.post(
        f"/screener/schemes/{scheme_id}/versions",
        json={
            "version_label": "v1",
            "change_note": "初始版本",
            "created_by": "tester",
            "config": {
                "universe_filter_config": {"board": "main"},
                "factor_selection_config": {"enabled_groups": ["trend", "quality"]},
                "factor_weight_config": {
                    "alpha": 0.5,
                    "trigger": 0.3,
                    "risk": 0.2,
                },
                "threshold_config": {"ready_min_score": 80},
                "quality_gate_config": {"drop_failed_quality": True},
                "bucket_rule_config": {"ready_bucket": "READY_TO_BUY"},
            },
        },
    )
    assert create_version.status_code == 200
    version_payload = create_version.json()
    assert version_payload["scheme_id"] == scheme_id
    assert version_payload["snapshot_hash"]

    detail = client.get(f"/screener/schemes/{scheme_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["scheme"]["current_version"] == version_payload["scheme_version"]
    assert detail_payload["current_version_detail"]["version_label"] == "v1"

    versions = client.get(f"/screener/schemes/{scheme_id}/versions")
    assert versions.status_code == 200
    versions_payload = versions.json()
    assert versions_payload["total"] == 1
    assert versions_payload["items"][0]["scheme_version"] == version_payload["scheme_version"]

    app.dependency_overrides.clear()


def test_get_missing_scheme_route_returns_404(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    app.dependency_overrides[get_screener_scheme_service] = lambda: service

    response = client.get("/screener/schemes/unknown-scheme")

    assert response.status_code == 404
    assert response.json()["detail"] == "Screener scheme not found."

    app.dependency_overrides.clear()


def test_get_missing_scheme_version_route_returns_404(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    app.dependency_overrides[get_screener_scheme_service] = lambda: service

    response = client.get("/screener/schemes/default_builtin_scheme/versions/missing-v1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Screener scheme version not found."

    app.dependency_overrides.clear()


class StubScreenerSchemeReviewService:
    def list_scheme_runs(
        self,
        *,
        scheme_id: str,
        started_from=None,
        started_to=None,
        limit: int = 20,
    ) -> ScreenerSchemeRunsResponse:
        assert scheme_id == "default_builtin_scheme"
        assert limit == 20
        return ScreenerSchemeRunsResponse(
            scheme_id=scheme_id,
            count=1,
            items=[
                ScreenerSchemeRunSummary(
                    batch_id="batch-1",
                    run_id="run-1",
                    trade_date=datetime(2026, 4, 21, tzinfo=timezone.utc).date(),
                    started_at=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
                    finished_at=datetime(2026, 4, 21, 9, 35, tzinfo=timezone.utc),
                    status="completed",
                    scheme_version="legacy_v1",
                    scheme_name="默认内置方案",
                    universe_size=50,
                    scanned_size=50,
                    result_count=2,
                    ready_count=1,
                    watch_count=0,
                    avoid_count=0,
                    research_count=1,
                    decision_snapshot_count=1,
                    trade_count=1,
                    review_count=1,
                )
            ],
        )

    def get_scheme_stats(
        self,
        *,
        scheme_id: str,
        started_from=None,
        started_to=None,
        limit: int = 100,
    ) -> ScreenerSchemeStatsResponse:
        assert scheme_id == "default_builtin_scheme"
        return ScreenerSchemeStatsResponse(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            stats=ScreenerSchemeStats(
                total_runs=1,
                completed_runs=1,
                failed_runs=0,
                running_runs=0,
                total_candidates=2,
                ready_count=1,
                watch_count=0,
                avoid_count=0,
                research_count=1,
                entered_research_count=1,
                decision_snapshot_count=1,
                trade_count=1,
                review_count=1,
                outcome_distribution={"success": 1},
                scheme_versions=["legacy_v1"],
                warning_messages=[],
            ),
        )

    def get_scheme_feedback(
        self,
        *,
        scheme_id: str,
        started_from=None,
        started_to=None,
        limit: int = 100,
    ) -> ScreenerSchemeReviewStatsResponse:
        assert scheme_id == "default_builtin_scheme"
        return ScreenerSchemeReviewStatsResponse(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            feedback=ScreenerSchemeFeedbackSummary(
                linked_symbols=2,
                traded_symbols=1,
                reviewed_symbols=1,
                aligned_trades=1,
                partially_aligned_trades=0,
                not_aligned_trades=0,
                did_follow_plan_distribution={"yes": 1},
                outcome_distribution={"success": 1},
                lesson_tag_distribution={"follow_plan": 1},
                warning_messages=[],
            ),
        )


def test_scheme_runs_route_returns_run_summaries() -> None:
    app.dependency_overrides[get_screener_scheme_review_service] = (
        lambda: StubScreenerSchemeReviewService()
    )

    response = client.get("/screener/schemes/default_builtin_scheme/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scheme_id"] == "default_builtin_scheme"
    assert payload["count"] == 1
    assert payload["items"][0]["batch_id"] == "batch-1"
    assert payload["items"][0]["decision_snapshot_count"] == 1

    app.dependency_overrides.clear()


def test_scheme_stats_route_returns_aggregate_stats() -> None:
    app.dependency_overrides[get_screener_scheme_review_service] = (
        lambda: StubScreenerSchemeReviewService()
    )

    response = client.get("/screener/schemes/default_builtin_scheme/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scheme_id"] == "default_builtin_scheme"
    assert payload["stats"]["total_runs"] == 1
    assert payload["stats"]["trade_count"] == 1
    assert payload["stats"]["outcome_distribution"]["success"] == 1

    app.dependency_overrides.clear()


def test_scheme_feedback_route_returns_feedback_summary() -> None:
    app.dependency_overrides[get_screener_scheme_review_service] = (
        lambda: StubScreenerSchemeReviewService()
    )

    response = client.get("/screener/schemes/default_builtin_scheme/feedback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scheme_id"] == "default_builtin_scheme"
    assert payload["feedback"]["linked_symbols"] == 2
    assert payload["feedback"]["did_follow_plan_distribution"]["yes"] == 1

    app.dependency_overrides.clear()
