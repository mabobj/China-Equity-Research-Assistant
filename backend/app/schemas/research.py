"""结构化研究输出相关 schema。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
