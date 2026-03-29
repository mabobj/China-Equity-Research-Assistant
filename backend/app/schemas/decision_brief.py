"""统一决策简报 schema。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRef


DecisionBriefAction = Literal[
    "BUY_NOW",
    "WAIT_PULLBACK",
    "WAIT_BREAKOUT",
    "RESEARCH_ONLY",
    "AVOID",
]
DecisionConvictionLevel = Literal["low", "medium", "high"]
DecisionSourceModuleName = Literal[
    "stock_profile",
    "factor_snapshot",
    "review_report",
    "debate_review",
    "strategy_plan",
    "trigger_snapshot",
]


class DecisionBriefEvidence(BaseModel):
    """可追溯的核心证据或风险。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    detail: str
    source_module: DecisionSourceModuleName
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class DecisionPriceLevel(BaseModel):
    """需要重点关注的价格位。"""

    model_config = ConfigDict(extra="forbid")

    label: str
    value_text: str
    note: Optional[str] = None


class DecisionSourceModule(BaseModel):
    """决策简报引用到的来源模块摘要。"""

    model_config = ConfigDict(extra="forbid")

    module_name: DecisionSourceModuleName
    as_of: Optional[str] = None
    note: Optional[str] = None


class DecisionBrief(BaseModel):
    """统一的结论 -> 依据 -> 动作 输出层。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    as_of_date: date
    freshness_mode: Optional[str] = None
    source_mode: Optional[str] = None
    headline_verdict: str
    action_now: DecisionBriefAction
    conviction_level: DecisionConvictionLevel
    why_it_made_the_list: list[str] = Field(default_factory=list, max_length=3)
    why_not_all_in: list[str] = Field(default_factory=list, max_length=3)
    key_evidence: list[DecisionBriefEvidence] = Field(default_factory=list, max_length=5)
    key_risks: list[DecisionBriefEvidence] = Field(default_factory=list, max_length=5)
    price_levels_to_watch: list[DecisionPriceLevel] = Field(default_factory=list)
    what_to_do_next: list[str] = Field(default_factory=list, max_length=3)
    next_review_window: str
    source_modules: list[DecisionSourceModule] = Field(default_factory=list)
    evidence_manifest_refs: list[EvidenceRef] = Field(default_factory=list)
