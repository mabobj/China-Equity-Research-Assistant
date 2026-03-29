"""Workspace bundle schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.debate import DebateReviewProgress, DebateReviewReport
from app.schemas.decision_brief import DecisionBrief
from app.schemas.evidence import EvidenceManifest
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import StockProfile
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan


ModuleStatus = Literal["success", "error", "skipped"]


class WorkspaceModuleStatus(BaseModel):
    """Status summary for one workspace module."""

    model_config = ConfigDict(extra="forbid")

    module_name: str
    status: ModuleStatus
    message: Optional[str] = None
    provider_used: Optional[str] = None
    provider_candidates: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    warning_messages: list[str] = Field(default_factory=list)


class WorkspaceFreshnessItem(BaseModel):
    """Freshness summary for one logical item."""

    model_config = ConfigDict(extra="forbid")

    item_name: str
    as_of_date: Optional[date] = None
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None


class FreshnessSummary(BaseModel):
    """Top-level freshness summary."""

    model_config = ConfigDict(extra="forbid")

    default_as_of_date: Optional[date] = None
    items: list[WorkspaceFreshnessItem] = Field(default_factory=list)


class WorkspaceBundleResponse(BaseModel):
    """Single-stock workspace bundle response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    use_llm: bool
    profile: Optional[StockProfile] = None
    factor_snapshot: Optional[FactorSnapshot] = None
    review_report: Optional[StockReviewReport] = None
    debate_review: Optional[DebateReviewReport] = None
    strategy_plan: Optional[StrategyPlan] = None
    trigger_snapshot: Optional[TriggerSnapshot] = None
    decision_brief: Optional[DecisionBrief] = None
    module_status_summary: list[WorkspaceModuleStatus] = Field(default_factory=list)
    evidence_manifest: Optional[EvidenceManifest] = None
    freshness_summary: FreshnessSummary = Field(default_factory=FreshnessSummary)
    debate_progress: Optional[DebateReviewProgress] = None
    provider_used: Optional[str] = None
    provider_candidates: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    runtime_mode_requested: Optional[str] = None
    runtime_mode_effective: Optional[str] = None
    warning_messages: list[str] = Field(default_factory=list)
