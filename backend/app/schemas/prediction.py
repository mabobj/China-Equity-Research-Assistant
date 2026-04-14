"""预测服务相关 schema（v2.1 第一步）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lineage import LineageMetadata


class PredictionSnapshotResponse(BaseModel):
    """单票预测快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    dataset_version: str
    model_version: str
    feature_version: str
    label_version: str
    predictive_score: int = Field(ge=0, le=100)
    upside_probability: float = Field(ge=0.0, le=1.0)
    expected_excess_return: float
    model_confidence: float = Field(ge=0.0, le=1.0)
    runtime_mode: Literal["baseline"]
    warning_messages: list[str] = Field(default_factory=list)
    generated_at: datetime
    lineage_metadata: Optional[LineageMetadata] = None


class CrossSectionPredictionRunRequest(BaseModel):
    """截面预测运行请求。"""

    model_config = ConfigDict(extra="forbid")

    max_symbols: int = Field(default=200, ge=1, le=5000)
    top_k: int = Field(default=30, ge=1, le=500)
    as_of_date: Optional[date] = None
    model_version: Optional[str] = None
    force_refresh: bool = False


class CrossSectionPredictionCandidate(BaseModel):
    """截面预测候选项。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    rank: int = Field(ge=1)
    predictive_score: int = Field(ge=0, le=100)
    model_confidence: float = Field(ge=0.0, le=1.0)
    expected_excess_return: float


class CrossSectionPredictionRunResponse(BaseModel):
    """截面预测运行结果。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["completed"]
    as_of_date: date
    dataset_version: str
    model_version: str
    feature_version: str
    label_version: str
    total_symbols: int = Field(ge=0)
    candidates: list[CrossSectionPredictionCandidate] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
    generated_at: datetime
    lineage_metadata: Optional[LineageMetadata] = None
