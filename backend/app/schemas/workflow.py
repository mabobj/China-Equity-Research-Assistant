"""Workflow v1 相关 schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.debate import DebateReviewReport, SingleStockResearchInputs
from app.schemas.factor import FactorSnapshot
from app.schemas.review import StockReviewReport
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.schemas.strategy import StrategyPlan

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
    "ReviewReportBuild",
    "DebateReviewBuild",
    "StrategyPlanBuild",
    "DeepCandidateSelect",
    "CandidateReviewBuild",
    "CandidateDebateBuild",
    "CandidateStrategyBuild",
]
WorkflowStepStatus = Literal["pending", "running", "completed", "failed", "skipped"]
WorkflowRunStatus = Literal["running", "completed", "failed"]


class WorkflowNodeRequest(BaseModel):
    """兼容旧占位接口的轻量节点请求。"""

    model_config = ConfigDict(extra="forbid")

    node_type: WorkflowNodeType
    symbol: Optional[str] = None
    run_id: Optional[str] = None


class WorkflowNodeResult(BaseModel):
    """兼容旧占位接口的轻量节点结果。"""

    model_config = ConfigDict(extra="forbid")

    node_type: WorkflowNodeType
    status: WorkflowStepStatus
    symbol: Optional[str] = None
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowRunRequest(BaseModel):
    """Workflow 通用运行参数。"""

    model_config = ConfigDict(extra="forbid")

    start_from: Optional[str] = None
    stop_after: Optional[str] = None
    use_llm: Optional[bool] = None


class SingleStockWorkflowRunRequest(WorkflowRunRequest):
    """单票完整研判 workflow 请求。"""

    symbol: str = Field(min_length=1)


class DeepReviewWorkflowRunRequest(WorkflowRunRequest):
    """深筛复核 workflow 请求。"""

    max_symbols: Optional[int] = Field(default=None, ge=1)
    top_n: Optional[int] = Field(default=None, ge=1)
    deep_top_k: Optional[int] = Field(default=None, ge=1)
    force_refresh: Optional[bool] = None


class ScreenerWorkflowRunRequest(WorkflowRunRequest):
    """初筛 workflow 请求。"""

    batch_size: Optional[int] = Field(default=None, ge=1)
    max_symbols: Optional[int] = Field(default=None, ge=1)
    top_n: Optional[int] = Field(default=None, ge=1)
    force_refresh: Optional[bool] = None


class WorkflowStepSummary(BaseModel):
    """单个 workflow 节点的执行摘要。"""

    model_config = ConfigDict(extra="forbid")

    node_name: str
    status: WorkflowStepStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class WorkflowSymbolFailure(BaseModel):
    """深筛 workflow 中单个标的失败摘要。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    step_name: str
    error_message: str


class SingleStockWorkflowOutput(BaseModel):
    """单票 workflow 的统一输出。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    research_inputs: Optional[SingleStockResearchInputs] = None
    factor_snapshot: Optional[FactorSnapshot] = None
    review_report: Optional[StockReviewReport] = None
    debate_review: Optional[DebateReviewReport] = None
    strategy_plan: Optional[StrategyPlan] = None


class DeepCandidateSelection(BaseModel):
    """深筛候选选择结果。"""

    model_config = ConfigDict(extra="forbid")

    selected_candidates: list[ScreenerCandidate] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)


class CandidateWorkflowItem(BaseModel):
    """深筛 workflow 中单个候选标的的聚合结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: Optional[str] = None
    base_candidate: Optional[ScreenerCandidate] = None
    review_report: Optional[StockReviewReport] = None
    debate_review: Optional[DebateReviewReport] = None
    strategy_plan: Optional[StrategyPlan] = None


class DeepReviewBatchOutput(BaseModel):
    """深筛批量节点的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    items: list[CandidateWorkflowItem] = Field(default_factory=list)
    failures: list[WorkflowSymbolFailure] = Field(default_factory=list)


class DeepReviewWorkflowOutput(BaseModel):
    """深筛 workflow 的统一输出。"""

    model_config = ConfigDict(extra="forbid")

    screener_run: Optional[ScreenerRunResponse] = None
    candidate_selection: Optional[DeepCandidateSelection] = None
    candidates: list[CandidateWorkflowItem] = Field(default_factory=list)
    failures: list[WorkflowSymbolFailure] = Field(default_factory=list)


class WorkflowRunResponse(BaseModel):
    """workflow 运行完成后的响应。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow_name: str
    status: WorkflowRunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStepSummary] = Field(default_factory=list)
    final_output_summary: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    accepted: bool = True
    existing_run_id: Optional[str] = None
    message: Optional[str] = None
    provider_used: Optional[str] = None
    provider_candidates: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    runtime_mode_requested: Optional[str] = None
    runtime_mode_effective: Optional[str] = None
    warning_messages: list[str] = Field(default_factory=list)
    failed_symbols: list[str] = Field(default_factory=list)


class WorkflowRunDetailResponse(WorkflowRunResponse):
    """workflow 运行详情响应。"""

    final_output: Optional[
        Union[
            SingleStockWorkflowOutput,
            DeepReviewWorkflowOutput,
            ScreenerRunResponse,
        ]
    ] = None
