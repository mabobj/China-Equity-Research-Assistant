"""回测相关 schema（v2.1 第一步）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lineage import LineageMetadata


class ScreenerBacktestRunRequest(BaseModel):
    """选股回测请求。"""

    model_config = ConfigDict(extra="forbid")

    model_version: Optional[str] = None
    lookback_days: int = Field(default=120, ge=20, le=1500)
    top_k: int = Field(default=20, ge=1, le=200)
    as_of_end: Optional[date] = None


class StrategyBacktestRunRequest(BaseModel):
    """策略回测请求。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    model_version: Optional[str] = None
    lookback_days: int = Field(default=120, ge=20, le=1500)
    as_of_end: Optional[date] = None


class BacktestRunResponse(BaseModel):
    """回测结果响应。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    dataset_version: str
    backtest_type: str
    model_version: str
    feature_version: Optional[str] = None
    label_version: Optional[str] = None
    window_start: date
    window_end: date
    metrics: dict[str, float] = Field(default_factory=dict)
    summary: str
    warning_messages: list[str] = Field(default_factory=list)
    finished_at: datetime
    lineage_metadata: Optional[LineageMetadata] = None
