"""Provider capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.schemas.provider import ProviderCapabilityReport, ProviderHealthReport
from app.services.data_service.providers.base import (
    MarketDataCapability,
    SessionScopedProvider,
    infer_provider_capabilities,
)


@dataclass(frozen=True)
class ProviderAdapter:
    """把现有 provider 对象适配成统一 registry 条目。"""

    raw_provider: object
    name: str
    capabilities: tuple[MarketDataCapability, ...]

    @classmethod
    def from_provider(cls, provider: object) -> "ProviderAdapter":
        provider_name = getattr(provider, "name", provider.__class__.__name__)
        return cls(
            raw_provider=provider,
            name=str(provider_name),
            capabilities=infer_provider_capabilities(provider),
        )

    def is_available(self) -> bool:
        available = getattr(self.raw_provider, "is_available", None)
        if callable(available):
            return bool(available())
        return True

    def get_unavailable_reason(self) -> Optional[str]:
        unavailable_reason = getattr(self.raw_provider, "get_unavailable_reason", None)
        if callable(unavailable_reason):
            return unavailable_reason()
        if self.is_available():
            return None
        return "Provider is unavailable."

    def is_session_scoped(self) -> bool:
        return isinstance(self.raw_provider, SessionScopedProvider)

    def __getattr__(self, item: str) -> object:
        return getattr(self.raw_provider, item)


class ProviderRegistry:
    """按 capability 管理 provider。"""

    def __init__(self, providers: Iterable[object]) -> None:
        self._providers = [ProviderAdapter.from_provider(provider) for provider in providers]

    def get_providers(
        self,
        capability: MarketDataCapability,
        available_only: bool = True,
    ) -> list[ProviderAdapter]:
        providers = [
            provider
            for provider in self._providers
            if capability in provider.capabilities
        ]
        if not available_only:
            return providers
        return [provider for provider in providers if provider.is_available()]

    def get_all_providers(self) -> list[ProviderAdapter]:
        return list(self._providers)

    def get_all_available_providers(self) -> list[ProviderAdapter]:
        return [provider for provider in self._providers if provider.is_available()]

    def get_capability_reports(self) -> list[ProviderCapabilityReport]:
        return [
            ProviderCapabilityReport(
                provider_name=provider.name,
                capabilities=list(provider.capabilities),
                session_scoped=provider.is_session_scoped(),
            )
            for provider in self._providers
        ]

    def get_health_reports(self) -> list[ProviderHealthReport]:
        return [
            ProviderHealthReport(
                provider_name=provider.name,
                available=provider.is_available(),
                unavailable_reason=provider.get_unavailable_reason(),
            )
            for provider in self._providers
        ]

