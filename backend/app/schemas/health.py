"""Schemas for health endpoints."""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Minimal health response payload."""

    model_config = ConfigDict(extra="forbid")

    status: str
