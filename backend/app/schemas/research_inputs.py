"""单票研究输入相关的 Pydantic Schema。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FinancialReportType = Literal["annual", "q1", "half", "q3", "ttm", "unknown"]
FinancialQualityStatus = Literal["ok", "warning", "degraded", "failed"]
AnnouncementQualityStatus = Literal["ok", "warning", "degraded", "failed"]


class AnnouncementItem(BaseModel):
    """单条公告列表项。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    title: str
    publish_date: date
    announcement_type: str = "other"
    announcement_subtype: Optional[str] = None
    source: str
    url: Optional[str] = None
    quality_status: Optional[AnnouncementQualityStatus] = None
    cleaning_warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    dedupe_key: Optional[str] = None
    as_of_date: Optional[date] = None


class AnnouncementListResponse(BaseModel):
    """公告列表响应。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    count: int = Field(ge=0)
    items: list[AnnouncementItem]
    quality_status: Optional[AnnouncementQualityStatus] = None
    cleaning_warnings: list[str] = Field(default_factory=list)
    dropped_rows: int = Field(default=0, ge=0)
    dropped_duplicate_rows: int = Field(default=0, ge=0)
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    as_of_date: Optional[date] = None


class FinancialSummary(BaseModel):
    """基础财务摘要（对外兼容结构）。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    report_period: Optional[date] = None
    report_type: Optional[FinancialReportType] = None
    revenue: Optional[float] = None
    revenue_yoy: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_yoy: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    source: str
    quality_status: Optional[FinancialQualityStatus] = None
    cleaning_warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    as_of_date: Optional[date] = None


class FinancialReportIndexItem(BaseModel):
    """Structured periodic financial report index item."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    report_period: Optional[date] = None
    report_type: Optional[FinancialReportType] = None
    title: str
    publish_date: date
    source: str
    url: Optional[str] = None


class FinancialReportIndexResponse(BaseModel):
    """Periodic financial report index response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    count: int = Field(ge=0)
    items: list[FinancialReportIndexItem]
