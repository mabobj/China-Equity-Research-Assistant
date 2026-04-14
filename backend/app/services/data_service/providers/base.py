"""Data provider capability protocols."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Optional, Protocol, runtime_checkable

from app.schemas.market_data import (
    DailyBar,
    IntradayBar,
    StockProfile,
    TimelinePoint,
    UniverseItem,
)
from app.schemas.research_inputs import (
    AnnouncementItem,
    FinancialReportIndexItem,
    FinancialSummary,
)

PROFILE_CAPABILITY = "profile"
DAILY_BAR_CAPABILITY = "daily_bars"
UNIVERSE_CAPABILITY = "universe"
ANNOUNCEMENT_CAPABILITY = "announcements"
FINANCIAL_SUMMARY_CAPABILITY = "financial_summary"
FINANCIAL_REPORT_INDEX_CAPABILITY = "financial_reports_index"
INTRADAY_BAR_CAPABILITY = "intraday_bars"
TIMELINE_CAPABILITY = "timeline"

MarketDataCapability = str


@runtime_checkable
class ProviderBase(Protocol):
    """Shared minimum provider protocol."""

    name: str
    capabilities: tuple[MarketDataCapability, ...]

    def is_available(self) -> bool:
        """Return whether provider is currently available."""

    def get_unavailable_reason(self) -> Optional[str]:
        """Return a stable unavailable reason when not available."""


@runtime_checkable
class SessionScopedProvider(Protocol):
    """Provider protocol for reusable batch sessions."""

    def session_scope(self) -> AbstractContextManager[None]:
        """Return a provider-scoped session context."""


@runtime_checkable
class ProfileProvider(ProviderBase, Protocol):
    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """Load a stock profile."""


@runtime_checkable
class DailyBarProvider(ProviderBase, Protocol):
    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        adjustment_mode: str = "raw",
    ) -> list[DailyBar]:
        """Load daily bars."""


@runtime_checkable
class UniverseProvider(ProviderBase, Protocol):
    def get_stock_universe(self) -> list[UniverseItem]:
        """Load the stock universe."""


@runtime_checkable
class AnnouncementProvider(ProviderBase, Protocol):
    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """Load stock announcements."""


@runtime_checkable
class FinancialSummaryProvider(ProviderBase, Protocol):
    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """Load a structured financial summary."""


@runtime_checkable
class FinancialReportIndexProvider(ProviderBase, Protocol):
    def get_financial_report_indexes(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[FinancialReportIndexItem]:
        """Load periodic report index items."""


@runtime_checkable
class IntradayBarProvider(ProviderBase, Protocol):
    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[IntradayBar]:
        """Load intraday bars."""


@runtime_checkable
class TimelineProvider(ProviderBase, Protocol):
    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> list[TimelinePoint]:
        """Load intraday timeline points."""


class MarketDataProvider(
    ProfileProvider,
    DailyBarProvider,
    UniverseProvider,
    AnnouncementProvider,
    FinancialSummaryProvider,
    Protocol,
):
    """Backward-compatible composite provider protocol."""


def infer_provider_capabilities(provider: object) -> tuple[MarketDataCapability, ...]:
    """Infer provider capabilities from an implementation object."""

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
    if hasattr(provider, "get_financial_report_indexes"):
        inferred.append(FINANCIAL_REPORT_INDEX_CAPABILITY)
    if hasattr(provider, "get_intraday_bars"):
        inferred.append(INTRADAY_BAR_CAPABILITY)
    if hasattr(provider, "get_timeline"):
        inferred.append(TIMELINE_CAPABILITY)
    return tuple(inferred)
