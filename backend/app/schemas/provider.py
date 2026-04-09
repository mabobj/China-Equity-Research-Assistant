"""Provider capability and health schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProviderCapabilityReport(BaseModel):
    """Structured provider capability report."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    capabilities: list[str]
    session_scoped: bool = False
    preferred_for: list[str] = Field(default_factory=list)
    fallback_for: list[str] = Field(default_factory=list)
    require_local_persistence_for: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProviderHealthReport(BaseModel):
    """Structured provider health report."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    available: bool
    unavailable_reason: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    health_status: str = "ok"
    warning_messages: list[str] = Field(default_factory=list)


class CapabilityPolicyReport(BaseModel):
    """Capability 级别的 provider 策略摘要。"""

    model_config = ConfigDict(extra="forbid")

    capability: str
    preferred_providers: list[str]
    allow_stale_fallback: bool
    require_local_persistence: bool
    notes: str
