"""因子服务内部基础类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.schemas.factor import FactorSnapshot
from app.schemas.market_data import DailyBar
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.schemas.technical import TechnicalSnapshot


@dataclass(frozen=True)
class FactorMetric:
    """单个因子度量结果。"""

    factor_name: str
    raw_value: Optional[float]
    normalized_score: Optional[float]
    positive_signal: Optional[str] = None
    negative_signal: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class FactorGroupResult:
    """单个因子组的聚合结果。"""

    group_name: str
    metrics: list[FactorMetric]
    score: Optional[float]


@dataclass(frozen=True)
class FactorBuildInputs:
    """构建因子快照所需的结构化输入。"""

    symbol: str
    technical_snapshot: TechnicalSnapshot
    daily_bars: list[DailyBar]
    financial_summary: Optional[FinancialSummary] = None
    announcements: list[AnnouncementItem] = field(default_factory=list)


class FactorSnapshotBuilder(Protocol):
    """从结构化输入构建因子快照。"""

    def build_from_inputs(self, inputs: FactorBuildInputs) -> FactorSnapshot:
        """构建单票因子快照。"""
