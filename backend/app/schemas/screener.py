"""Schemas for screener outputs."""

from pydantic import BaseModel, ConfigDict


class ScreenerResult(BaseModel):
    """Machine-readable screener output schema."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    screener_score: float
    rank: int
    list_type: str
    short_reason: str
