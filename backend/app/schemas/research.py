"""结构化研究输出相关 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

QualityStatus = Literal["ok", "warning", "degraded", "failed"]


class TechnicalResearchResult(BaseModel):
    """技术研究中间结果。"""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    summary: str
    key_reasons: list[str]
    risks: list[str]
    triggers: list[str]
    invalidations: list[str]


class FundamentalResearchResult(BaseModel):
    """基本面研究中间结果。"""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    summary: str
    key_reasons: list[str]
    risks: list[str]
    triggers: list[str]
    invalidations: list[str]


class EventResearchResult(BaseModel):
    """公告事件研究中间结果。"""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    summary: str
    key_reasons: list[str]
    risks: list[str]
    triggers: list[str]
    invalidations: list[str]


class ResearchDataQualitySummary(BaseModel):
    """研究链路的数据质量摘要。"""

    model_config = ConfigDict(extra="forbid")

    bars_quality: QualityStatus
    financial_quality: QualityStatus
    announcement_quality: QualityStatus
    technical_modifier: float = Field(ge=0, le=1)
    fundamental_modifier: float = Field(ge=0, le=1)
    event_modifier: float = Field(ge=0, le=1)
    overall_quality_modifier: float = Field(ge=0, le=1)


class ResearchReport(BaseModel):
    """结构化单票研究报告。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    as_of_date: date
    technical_score: int = Field(ge=0, le=100)
    fundamental_score: int = Field(ge=0, le=100)
    event_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    action: Literal["BUY", "WATCH", "AVOID"]
    confidence: int = Field(ge=0, le=100)
    thesis: str
    key_reasons: list[str]
    risks: list[str]
    triggers: list[str]
    invalidations: list[str]
    data_quality_summary: Optional[ResearchDataQualitySummary] = None
    confidence_reasons: list[str] = Field(default_factory=list)
