"""数据 provider 共用协议。"""

from datetime import date
from typing import Optional, Protocol

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import (
    AnnouncementItem,
    FinancialSummary,
)


class MarketDataProvider(Protocol):
    """市场数据 provider 最小协议。"""

    name: str

    def is_available(self) -> bool:
        """返回当前 provider 是否可用。"""

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """获取单只股票基础信息。"""

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """获取单只股票日线行情。"""

    def get_stock_universe(self) -> list[UniverseItem]:
        """获取基础股票池。"""

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """获取单只股票公告列表。"""

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """获取单只股票基础财务摘要。"""
