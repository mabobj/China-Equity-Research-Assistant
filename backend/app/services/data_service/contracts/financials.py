"""Financial summary 清洗后的内部契约。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.research_inputs import FinancialSummary

FinancialQualityStatus = Literal["ok", "warning", "degraded", "failed"]
FinancialReportType = Literal["annual", "q1", "half", "q3", "ttm", "unknown"]


class FinancialSummaryCleaningSummary(BaseModel):
    """财务摘要清洗摘要。"""

    model_config = ConfigDict(extra="forbid")

    quality_status: FinancialQualityStatus
    total_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    dropped_rows: int = Field(ge=0)
    dropped_duplicate_rows: int = Field(ge=0)
    warning_messages: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)


class CleanFinancialSummary(BaseModel):
    """清洗后的财务摘要对象。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: Optional[str] = None
    report_period: Optional[date] = None
    report_type: FinancialReportType = "unknown"
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
    as_of_date: date
    quality_status: FinancialQualityStatus = "ok"
    cleaning_warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None

    def to_financial_summary(self) -> FinancialSummary:
        """转换为对外兼容的 FinancialSummary。"""
        return FinancialSummary(
            symbol=self.symbol,
            name=self.name or self.symbol,
            report_period=self.report_period,
            report_type=self.report_type,
            revenue=self.revenue,
            revenue_yoy=self.revenue_yoy,
            net_profit=self.net_profit,
            net_profit_yoy=self.net_profit_yoy,
            roe=self.roe,
            gross_margin=self.gross_margin,
            debt_ratio=self.debt_ratio,
            eps=self.eps,
            bps=self.bps,
            source=self.source,
            quality_status=self.quality_status,
            cleaning_warnings=list(self.cleaning_warnings),
            missing_fields=list(self.missing_fields),
            coerced_fields=list(self.coerced_fields),
            provider_used=self.provider_used,
            fallback_applied=self.fallback_applied,
            fallback_reason=self.fallback_reason,
            source_mode=self.source_mode,
            freshness_mode=self.freshness_mode,
            as_of_date=self.as_of_date,
        )


class CleanFinancialSummaryResult(BaseModel):
    """财务摘要清洗结果。"""

    model_config = ConfigDict(extra="forbid")

    summary: Optional[CleanFinancialSummary] = None
    cleaning_summary: FinancialSummaryCleaningSummary
