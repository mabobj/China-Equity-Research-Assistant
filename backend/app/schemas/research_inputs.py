"""单票研究输入相关的 Pydantic Schema。"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AnnouncementItem(BaseModel):
    """单条公告列表项。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    title: str
    publish_date: date
    announcement_type: str
    source: str
    url: str


class AnnouncementListResponse(BaseModel):
    """公告列表响应。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    count: int = Field(ge=0)
    items: list[AnnouncementItem]


class FinancialSummary(BaseModel):
    """基础财务摘要。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    report_period: Optional[date] = None
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
