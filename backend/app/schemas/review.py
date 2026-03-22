"""Schemas for review records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewRecord(BaseModel):
    """Structured review record schema."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    reviewed_at: datetime
    summary: str
    lessons: list[str]
    next_actions: list[str]
