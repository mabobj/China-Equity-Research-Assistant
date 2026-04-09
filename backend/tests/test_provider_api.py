"""Provider 诊断 API 测试。"""

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_data_service
from app.main import app
from app.schemas.provider import CapabilityHealthReport, CapabilityPolicyReport


class StubProviderDiagnosticsService:
    def get_capability_policy_reports(self) -> list[CapabilityPolicyReport]:
        return [
            CapabilityPolicyReport(
                capability="daily_bars",
                preferred_providers=["tdx_api", "mootdx", "akshare", "baostock"],
                allow_stale_fallback=True,
                require_local_persistence=True,
                notes="日线主链路优先本地或局域网源。",
            )
        ]

    def get_capability_health_reports(self) -> list[CapabilityHealthReport]:
        return [
            CapabilityHealthReport(
                capability="daily_bars",
                preferred_providers=["tdx_api", "mootdx", "akshare", "baostock"],
                configured_providers=["tdx_api", "mootdx"],
                available_providers=["mootdx"],
                selected_provider="mootdx",
                allow_stale_fallback=True,
                require_local_persistence=True,
                local_persistence_available=True,
                health_status="degraded",
                warning_messages=["主用 provider 当前不可用，当前将使用 fallback provider。"],
            )
        ]

    def get_capability_health_report(self, capability: str) -> CapabilityHealthReport:
        assert capability == "daily_bars"
        return self.get_capability_health_reports()[0]


client = TestClient(app)


def setup_module(module) -> None:  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_market_data_service] = (
        lambda: StubProviderDiagnosticsService()
    )


def teardown_module(module) -> None:  # type: ignore[no-untyped-def]
    app.dependency_overrides.clear()


def test_get_provider_capabilities() -> None:
    response = client.get("/providers/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["capability"] == "daily_bars"
    assert payload[0]["preferred_providers"][0] == "tdx_api"


def test_get_provider_health_reports() -> None:
    response = client.get("/providers/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["capability"] == "daily_bars"
    assert payload[0]["selected_provider"] == "mootdx"
    assert payload[0]["health_status"] == "degraded"


def test_get_single_provider_health_report() -> None:
    response = client.get("/providers/health/daily_bars")

    assert response.status_code == 200
    payload = response.json()
    assert payload["capability"] == "daily_bars"
    assert payload["selected_provider"] == "mootdx"
