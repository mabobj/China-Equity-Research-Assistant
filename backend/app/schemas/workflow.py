"""Workflow node schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


WorkflowNodeType = Literal[
    "MarketDataSync",
    "FactorSnapshotBuild",
    "ScreenerRun",
    "CandidateDeepReview",
    "SingleStockResearch",
    "SingleStockResearchInputs",
    "AnalystViewsBuild",
    "BullBearDebateBuild",
    "ChiefJudgementBuild",
    "StrategyFinalize",
    "SingleStockStrategy",
]


class WorkflowNodeRequest(BaseModel):
    """Lightweight workflow node request."""

    model_config = ConfigDict(extra="forbid")

    node_type: WorkflowNodeType
    symbol: Optional[str] = None
    run_id: Optional[str] = None


class WorkflowNodeResult(BaseModel):
    """Lightweight workflow node result."""

    model_config = ConfigDict(extra="forbid")

    node_type: WorkflowNodeType
    status: Literal["pending", "running", "completed", "failed"]
    symbol: Optional[str] = None
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
