"""Schemas for market data responses."""

from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StockProfile(BaseModel):
    """Basic profile for one A-share stock."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    code: str
    exchange: Literal["SH", "SZ"]
    name: str
    industry: Optional[str] = None
    list_date: Optional[date] = None
    status: Optional[str] = None
    total_market_cap: Optional[float] = None
    circulating_market_cap: Optional[float] = None
    source: str


class DailyBar(BaseModel):
    """One daily OHLCV bar."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    adjustment_mode: Literal["raw", "qfq", "hfq"] = "raw"
    trading_status: Optional[str] = None
    corporate_action_flags: list[str] = Field(default_factory=list)
    source: str


class DailyBarResponse(BaseModel):
    """Daily bars response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    count: int = Field(ge=0)
    bars: list[DailyBar]
    quality_status: Optional[str] = None
    cleaning_warnings: list[str] = Field(default_factory=list)
    dropped_rows: int = Field(default=0, ge=0)
    dropped_duplicate_rows: int = Field(default=0, ge=0)
    adjustment_mode: Literal["raw", "qfq", "hfq"] = "raw"
    corporate_action_mode: Literal["unmodeled", "flags_only"] = "unmodeled"
    corporate_action_warnings: list[str] = Field(default_factory=list)


class IntradayBar(BaseModel):
    """One intraday OHLCV bar."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    trade_datetime: datetime
    frequency: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    source: str


class IntradayBarResponse(BaseModel):
    """Intraday bars response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    frequency: str
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    count: int = Field(ge=0)
    bars: list[IntradayBar]


class TimelinePoint(BaseModel):
    """One timeline point."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    trade_time: time
    price: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    source: str


class TimelineResponse(BaseModel):
    """Timeline response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    count: int = Field(ge=0)
    points: list[TimelinePoint]


class UniverseItem(BaseModel):
    """One stock entry in the basic universe list."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    code: str
    exchange: Literal["SH", "SZ"]
    name: str
    status: Optional[str] = None
    source: str


class UniverseResponse(BaseModel):
    """Universe list response."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    items: list[UniverseItem]
