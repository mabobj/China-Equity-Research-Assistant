"""Bars 清洗后的内部契约。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_data import DailyBar

BarQualityStatus = Literal["ok", "warning", "degraded", "failed"]


class DailyBarsCleaningSummary(BaseModel):
    """日线清洗摘要。"""

    model_config = ConfigDict(extra="forbid")

    quality_status: BarQualityStatus
    total_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    dropped_rows: int = Field(ge=0)
    dropped_duplicate_rows: int = Field(ge=0)
    warning_messages: list[str] = Field(default_factory=list)


class CleanDailyBar(BaseModel):
    """清洗后的单根日线。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None
    pct_change: Optional[float] = None
    adjustment_mode: Literal["raw", "qfq", "hfq"] = "raw"
    trading_status: Optional[str] = None
    corporate_action_flags: list[str] = Field(default_factory=list)
    source: str
    as_of_date: date
    quality_status: BarQualityStatus
    cleaning_warnings: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    def to_daily_bar(self) -> DailyBar:
        """转换为对外统一日线 schema。"""
        return DailyBar(
            symbol=self.symbol,
            trade_date=self.trade_date,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            amount=self.amount,
            adjustment_mode=self.adjustment_mode,
            trading_status=self.trading_status,
            corporate_action_flags=self.corporate_action_flags,
            source=self.source,
        )


class CleanDailyBarsResult(BaseModel):
    """批量日线清洗结果。"""

    model_config = ConfigDict(extra="forbid")

    bars: list[CleanDailyBar] = Field(default_factory=list)
    summary: DailyBarsCleaningSummary

    def to_daily_bars(self) -> list[DailyBar]:
        """转换为对外/存储使用的日线列表。"""
        return [item.to_daily_bar() for item in self.bars]
