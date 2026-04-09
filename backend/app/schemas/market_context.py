"""市场上下文与关键数据域 schema。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


BoardType = Literal["main_board", "chinext", "star_market", "unknown"]
BenchmarkCategory = Literal[
    "broad_market",
    "large_cap",
    "mid_cap",
    "small_cap",
    "growth",
]
QualityStatus = Literal["ok", "warning", "degraded", "failed"]
RiskRegime = Literal["risk_on", "neutral", "risk_off"]


class BenchmarkDefinition(BaseModel):
    """一个标准基准定义。"""

    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    symbol: str
    name: str
    exchange: Literal["SH", "SZ"]
    category: BenchmarkCategory
    is_primary: bool = False
    description: Optional[str] = None


class BenchmarkCatalogResponse(BaseModel):
    """基准目录响应。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    count: int = Field(ge=0)
    items: list[BenchmarkDefinition]
    source_mode: str = "static_catalog"
    freshness_mode: str = "static"


class StockClassificationSnapshot(BaseModel):
    """单票行业/板块分类快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: Literal["SH", "SZ"]
    board: BoardType
    industry: Optional[str] = None
    as_of_date: date
    quality_status: QualityStatus
    warning_messages: list[str] = Field(default_factory=list)
    source_mode: str = "derived_from_profile"
    freshness_mode: str = "snapshot"
    primary_benchmark_symbol: Optional[str] = None
    primary_benchmark_name: Optional[str] = None


class MarketBreadthSnapshot(BaseModel):
    """市场广度快照。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    universe_size: int = Field(ge=0)
    symbols_considered: int = Field(ge=0)
    symbols_skipped: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    advance_count: int = Field(ge=0)
    decline_count: int = Field(ge=0)
    flat_count: int = Field(ge=0)
    advance_ratio: float = Field(ge=0.0, le=1.0)
    decline_ratio: float = Field(ge=0.0, le=1.0)
    above_ma20_count: int = Field(ge=0)
    above_ma20_ratio: float = Field(ge=0.0, le=1.0)
    above_ma60_count: int = Field(ge=0)
    above_ma60_ratio: float = Field(ge=0.0, le=1.0)
    new_20d_high_count: int = Field(ge=0)
    new_20d_low_count: int = Field(ge=0)
    mean_return_1d: Optional[float] = None
    median_return_1d: Optional[float] = None
    breadth_score: float = Field(ge=0.0, le=100.0)
    quality_status: QualityStatus
    warning_messages: list[str] = Field(default_factory=list)
    source_mode: str
    freshness_mode: str


class RiskProxySnapshot(BaseModel):
    """基础风险代理快照。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    universe_size: int = Field(ge=0)
    symbols_considered: int = Field(ge=0)
    breadth_score: float = Field(ge=0.0, le=100.0)
    cross_sectional_volatility_1d: Optional[float] = None
    median_return_1d: Optional[float] = None
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_regime: RiskRegime
    quality_status: QualityStatus
    warning_messages: list[str] = Field(default_factory=list)
    source_mode: str
    freshness_mode: str
