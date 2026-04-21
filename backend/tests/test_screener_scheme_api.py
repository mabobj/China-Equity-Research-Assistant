"""API tests for screener scheme routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dependencies import get_screener_scheme_service
from app.main import app
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
