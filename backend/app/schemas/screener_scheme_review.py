"""Read-only scheme-level review and feedback schemas for factor-first screener."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ScreenerSchemeRunSummary(BaseModel):
    """Summary of one screener batch under a scheme."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    run_id: str
    trade_date: date
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    scheme_version: str | None = None
    scheme_name: str | None = None
    universe_size: int = Field(default=0, ge=0)
    scanned_size: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    ready_count: int = Field(default=0, ge=0)
    watch_count: int = Field(default=0, ge=0)
    avoid_count: int = Field(default=0, ge=0)
    research_count: int = Field(default=0, ge=0)
    decision_snapshot_count: int = Field(default=0, ge=0)
    trade_count: int = Field(default=0, ge=0)
    review_count: int = Field(default=0, ge=0)
    warning_messages: list[str] = Field(default_factory=list)
    failure_reason: str | None = None


class ScreenerSchemeRunsResponse(BaseModel):
    """List response for scheme run summaries."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    count: int = Field(ge=0)
    items: list[ScreenerSchemeRunSummary] = Field(default_factory=list)


class ScreenerSchemeStats(BaseModel):
    """Aggregated scheme-level stats for first-stage review."""

    model_config = ConfigDict(extra="forbid")

    total_runs: int = Field(default=0, ge=0)
    completed_runs: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    running_runs: int = Field(default=0, ge=0)
    total_candidates: int = Field(default=0, ge=0)
    ready_count: int = Field(default=0, ge=0)
    watch_count: int = Field(default=0, ge=0)
    avoid_count: int = Field(default=0, ge=0)
    research_count: int = Field(default=0, ge=0)
    entered_research_count: int = Field(default=0, ge=0)
    decision_snapshot_count: int = Field(default=0, ge=0)
    trade_count: int = Field(default=0, ge=0)
    review_count: int = Field(default=0, ge=0)
    outcome_distribution: dict[str, int] = Field(default_factory=dict)
    scheme_versions: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)


class ScreenerSchemeStatsResponse(BaseModel):
    """Response for scheme-level aggregate stats."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    started_from: datetime | None = None
    started_to: datetime | None = None
    stats: ScreenerSchemeStats


class ScreenerSchemeFeedbackSummary(BaseModel):
    """Feedback aggregation for trades and reviews linked back to a scheme."""

    model_config = ConfigDict(extra="forbid")

    linked_symbols: int = Field(default=0, ge=0)
    traded_symbols: int = Field(default=0, ge=0)
    reviewed_symbols: int = Field(default=0, ge=0)
    aligned_trades: int = Field(default=0, ge=0)
    partially_aligned_trades: int = Field(default=0, ge=0)
    not_aligned_trades: int = Field(default=0, ge=0)
    did_follow_plan_distribution: dict[str, int] = Field(default_factory=dict)
    outcome_distribution: dict[str, int] = Field(default_factory=dict)
    lesson_tag_distribution: dict[str, int] = Field(default_factory=dict)
    warning_messages: list[str] = Field(default_factory=list)


class ScreenerSchemeReviewStatsResponse(BaseModel):
    """Response for scheme-level review feedback summary."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    started_from: datetime | None = None
    started_to: datetime | None = None
    feedback: ScreenerSchemeFeedbackSummary
