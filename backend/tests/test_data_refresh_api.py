"""数据补全 API 测试。"""

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.dependencies import get_data_refresh_service
from app.main import app
from app.schemas.data_refresh import DataRefreshStatus


class StubDataRefreshService:
    """用于数据补全 API 测试的 service 桩。"""

    def __init__(self) -> None:
        self.started_with = None

    def get_status(self) -> DataRefreshStatus:
        return DataRefreshStatus(
            status="running",
            is_running=True,
            started_at=datetime(2026, 3, 24, 9, 0, 0),
            finished_at=None,
            universe_count=5491,
            total_symbols=200,
            processed_symbols=48,
            succeeded_symbols=45,
            failed_symbols=3,
            profiles_updated=45,
            daily_bars_updated=45,
            financial_summaries_updated=45,
            announcements_updated=45,
            daily_bars_synced_rows=1234,
            announcements_synced_items=678,
            profile_step_failures=1,
            daily_bar_step_failures=2,
            financial_step_failures=0,
            announcement_step_failures=1,
            universe_updated=True,
            max_symbols=200,
            current_symbol="600519.SH",
            current_stage="refresh_symbol",
            message="正在补全 48/200: 600519.SH",
            recent_warnings=["000001.SZ [日线数据] ProviderError: failed"],
            recent_errors=["000001.SZ: profile failed"],
        )

    def start_manual_refresh(self, max_symbols=None) -> DataRefreshStatus:
        self.started_with = max_symbols
        return self.get_status()


client = TestClient(app)


def test_get_data_refresh_status_route_returns_structured_payload() -> None:
    """状态接口应返回结构化补全状态。"""
    stub = StubDataRefreshService()
    app.dependency_overrides[get_data_refresh_service] = lambda: stub

    response = client.get("/data/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["universe_count"] == 5491
    assert payload["current_symbol"] == "600519.SH"

    app.dependency_overrides.clear()


def test_start_data_refresh_route_accepts_request_body() -> None:
    """启动接口应接收请求体并返回任务状态。"""
    stub = StubDataRefreshService()
    app.dependency_overrides[get_data_refresh_service] = lambda: stub

    response = client.post("/data/refresh", json={"max_symbols": 300})

    assert response.status_code == 202
    assert stub.started_with == 300
    assert response.json()["total_symbols"] == 200

    app.dependency_overrides.clear()
