"""Tests for provider capability registry."""

from typing import Optional

from app.services.data_service.provider_registry import ProviderRegistry


class ProfileOnlyProvider:
    name = "profile_only"
    capabilities = ("profile",)

    def is_available(self) -> bool:
        return True

    def get_unavailable_reason(self) -> Optional[str]:
        return None

    def get_stock_profile(self, symbol: str):
        return None


class DailyOnlyUnavailableProvider:
    name = "daily_only_unavailable"
    capabilities = ("daily_bars",)

    def is_available(self) -> bool:
        return False

    def get_unavailable_reason(self) -> Optional[str]:
        return "mock unavailable"

    def get_daily_bars(self, symbol: str, start_date=None, end_date=None):
        return []


def test_provider_registry_filters_by_capability_and_availability() -> None:
    registry = ProviderRegistry([ProfileOnlyProvider(), DailyOnlyUnavailableProvider()])

    profile_providers = registry.get_providers("profile")
    daily_providers = registry.get_providers("daily_bars")
    daily_providers_all = registry.get_providers("daily_bars", available_only=False)

    assert [provider.name for provider in profile_providers] == ["profile_only"]
    assert daily_providers == []
    assert [provider.name for provider in daily_providers_all] == ["daily_only_unavailable"]


def test_provider_registry_builds_reports() -> None:
    registry = ProviderRegistry([ProfileOnlyProvider(), DailyOnlyUnavailableProvider()])

    capability_reports = registry.get_capability_reports()
    health_reports = registry.get_health_reports()

    assert capability_reports[0].provider_name == "profile_only"
    assert capability_reports[0].capabilities == ["profile"]
    assert health_reports[1].provider_name == "daily_only_unavailable"
    assert health_reports[1].available is False
    assert health_reports[1].unavailable_reason == "mock unavailable"

