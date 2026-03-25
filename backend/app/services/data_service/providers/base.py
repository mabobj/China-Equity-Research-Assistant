"""数据 provider capability 协议。"""

from contextlib import AbstractContextManager
from datetime import date
from typing import Optional, Protocol, runtime_checkable

from app.schemas.market_data import (
    DailyBar,
    IntradayBar,
    StockProfile,
    TimelinePoint,
    UniverseItem,
)
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary

PROFILE_CAPABILITY = "profile"
DAILY_BAR_CAPABILITY = "daily_bars"
UNIVERSE_CAPABILITY = "universe"
ANNOUNCEMENT_CAPABILITY = "announcements"
FINANCIAL_SUMMARY_CAPABILITY = "financial_summary"
INTRADAY_BAR_CAPABILITY = "intraday_bars"
TIMELINE_CAPABILITY = "timeline"

MarketDataCapability = str


@runtime_checkable
class ProviderBase(Protocol):
    """所有 provider 共享的最小协议。"""

    name: str
    capabilities: tuple[MarketDataCapability, ...]

    def is_available(self) -> bool:
        """返回当前 provider 是否可用。"""

    def get_unavailable_reason(self) -> Optional[str]:
        """返回 provider 不可用时的原因。"""


@runtime_checkable
class SessionScopedProvider(Protocol):
    """支持批量会话复用的 provider 协议。"""

    def session_scope(self) -> AbstractContextManager[None]:
        """返回 provider 会话上下文。"""


@runtime_checkable
class ProfileProvider(ProviderBase, Protocol):
    """基础信息 provider。"""

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """获取单只股票基础信息。"""


@runtime_checkable
class DailyBarProvider(ProviderBase, Protocol):
    """日线行情 provider。"""

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """获取单只股票日线。"""


@runtime_checkable
class UniverseProvider(ProviderBase, Protocol):
    """股票池 provider。"""

    def get_stock_universe(self) -> list[UniverseItem]:
        """获取基础股票池。"""


@runtime_checkable
class AnnouncementProvider(ProviderBase, Protocol):
    """公告列表 provider。"""

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """获取公告列表。"""


@runtime_checkable
class FinancialSummaryProvider(ProviderBase, Protocol):
    """财务摘要 provider。"""

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """获取基础财务摘要。"""


@runtime_checkable
class IntradayBarProvider(ProviderBase, Protocol):
    """分钟线 provider。"""

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: Optional[int] = None,
    ) -> list[IntradayBar]:
        """获取单只股票分钟线。"""


@runtime_checkable
class TimelineProvider(ProviderBase, Protocol):
    """分时线 provider。"""

    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> list[TimelinePoint]:
        """获取单只股票分时线。"""


class MarketDataProvider(
    ProfileProvider,
    DailyBarProvider,
    UniverseProvider,
    AnnouncementProvider,
    FinancialSummaryProvider,
    Protocol,
):
    """兼容旧版 MarketDataService 的大协议。"""


def infer_provider_capabilities(provider: object) -> tuple[MarketDataCapability, ...]:
    """从 provider 对象推断其已实现的 capability。"""
    explicit_capabilities = getattr(provider, "capabilities", None)
    if explicit_capabilities:
        return tuple(str(item) for item in explicit_capabilities)

    inferred: list[MarketDataCapability] = []
    if hasattr(provider, "get_stock_profile"):
        inferred.append(PROFILE_CAPABILITY)
    if hasattr(provider, "get_daily_bars"):
        inferred.append(DAILY_BAR_CAPABILITY)
    if hasattr(provider, "get_stock_universe"):
        inferred.append(UNIVERSE_CAPABILITY)
    if hasattr(provider, "get_stock_announcements"):
        inferred.append(ANNOUNCEMENT_CAPABILITY)
    if hasattr(provider, "get_stock_financial_summary"):
        inferred.append(FINANCIAL_SUMMARY_CAPABILITY)
    if hasattr(provider, "get_intraday_bars"):
        inferred.append(INTRADAY_BAR_CAPABILITY)
    if hasattr(provider, "get_timeline"):
        inferred.append(TIMELINE_CAPABILITY)
    return tuple(inferred)

