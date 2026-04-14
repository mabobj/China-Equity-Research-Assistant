"""模型评估相关 schema（v2.1）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lineage import LineageMetadata


class EvaluationBacktestReference(BaseModel):
    """评估引用的回测结果摘要。"""

    model_config = ConfigDict(extra="forbid")

    backtest_type: str
    run_id: str
    window_start: date
    window_end: date
    metrics: dict[str, float] = Field(default_factory=dict)
    summary: str


class ModelEvaluationComparison(BaseModel):
    """与基线模型版本的指标差异。"""

    model_config = ConfigDict(extra="forbid")

    baseline_model_version: str
    compared_model_version: str
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    summary: str


class ModelVersionRecommendation(BaseModel):
    """模型版本建议摘要。"""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["promote_candidate", "keep_baseline", "observe"]
    recommended_model_version: str
    reason: str
    supporting_metrics: dict[str, float] = Field(default_factory=dict)
    guardrails: list[str] = Field(default_factory=list)


class ModelEvaluationResponse(BaseModel):
    """模型评估摘要响应。"""

    model_config = ConfigDict(extra="forbid")

    model_version: str
    feature_version: str
    label_version: str
    evaluated_at: datetime
    window_start: date
    window_end: date
    metrics: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
    backtest_references: list[EvaluationBacktestReference] = Field(
        default_factory=list
    )
    comparison: Optional[ModelEvaluationComparison] = None
    recommendation: Optional[ModelVersionRecommendation] = None
    dataset_version: Optional[str] = None
    lineage_metadata: Optional[LineageMetadata] = None
