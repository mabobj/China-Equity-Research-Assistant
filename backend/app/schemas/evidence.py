"""Structured evidence chain schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


EvidenceDataset = Literal[
    "daily_bars_daily",
    "announcements_daily",
    "financial_summary_daily",
    "factor_snapshot_daily",
    "review_report_daily",
    "debate_review_daily",
    "strategy_plan_daily",
    "decision_brief_daily",
    "screener_snapshot_daily",
]

EvidenceUsedBy = Literal[
    "decision_brief",
    "workspace_bundle",
    "screener_candidate",
    "review_report",
    "strategy_plan",
]


class EvidenceRef(BaseModel):
    """One traceable evidence reference."""

    model_config = ConfigDict(extra="forbid")

    dataset: EvidenceDataset
    provider: str
    symbol: str
    as_of_date: date
    field_path: str
    raw_value: Optional[Union[str, int, float, bool]] = None
    derived_value: Optional[Union[str, int, float, bool]] = None
    used_by: EvidenceUsedBy
    note: Optional[str] = None


class EvidenceBundle(BaseModel):
    """Evidence refs grouped by one business output."""

    model_config = ConfigDict(extra="forbid")

    bundle_name: str
    used_by: EvidenceUsedBy
    refs: list[EvidenceRef] = Field(default_factory=list)


class EvidenceManifest(BaseModel):
    """Top-level evidence manifest for one response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    bundles: list[EvidenceBundle] = Field(default_factory=list)
