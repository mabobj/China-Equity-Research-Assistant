"""Provider capability and health schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProviderCapabilityReport(BaseModel):
    """Structured provider capability report."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    capabilities: list[str]
    session_scoped: bool = False


class ProviderHealthReport(BaseModel):
    """Structured provider health report."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    available: bool
    unavailable_reason: Optional[str] = None

