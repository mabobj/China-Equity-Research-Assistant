"""Schemas for research outputs."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ResearchReport(BaseModel):
    """Structured single-stock research report schema."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    technical_score: float
    fundamental_score: float
    event_score: float
    risk_score: float
    overall_score: float
    action: str
    confidence: float
    thesis: str
    key_reasons: list[str]
    triggers: list[str]
    invalidations: list[str]
