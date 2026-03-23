"""A 股数据 service 层。"""

from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from app.schemas.market_data import DailyBarResponse, StockProfile, UniverseResponse
from app.schemas.research_inputs import (
    AnnouncementListResponse,
    FinancialSummary,
)
from app.services.data_service.exceptions import (
    DataNotFoundError,
    InvalidDateError,
    InvalidRequestError,
    ProviderError,
)
from app.services.data_service.normalize import normalize_symbol
from app.services.data_service.providers.base import MarketDataProvider


class MarketDataService:
    """统一封装 A 股数据访问与简单 fallback。"""

    def __init__(self, providers: Sequence[MarketDataProvider]) -> None:
        self._providers = list(providers)

    def get_stock_profile(self, symbol: str) -> StockProfile:
        """获取单只股票基础信息。"""
        canonical_symbol = normalize_symbol(symbol)
        last_error = None

        for provider in self._iter_available_providers():
            try:
                profile = provider.get_stock_profile(canonical_symbol)
            except ProviderError as exc:
                last_error = exc
                continue

            if profile is not None:
                return profile

        if last_error is not None:
            raise ProviderError(
                "Failed to load stock profile for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No stock profile found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        """获取单只股票日线行情。"""
        canonical_symbol = normalize_symbol(symbol)
        normalized_start_date = _parse_optional_date(start_date, "start_date")
        normalized_end_date = _parse_optional_date(end_date, "end_date")

        if (
            normalized_start_date is not None
            and normalized_end_date is not None
            and normalized_start_date > normalized_end_date
        ):
            raise InvalidDateError("start_date cannot be later than end_date.")

        last_error = None
        for provider in self._iter_available_providers():
            try:
                bars = provider.get_daily_bars(
                    canonical_symbol,
                    start_date=normalized_start_date,
                    end_date=normalized_end_date,
                )
            except ProviderError as exc:
                last_error = exc
                continue

            if bars:
                return DailyBarResponse(
                    symbol=canonical_symbol,
                    start_date=normalized_start_date,
                    end_date=normalized_end_date,
                    count=len(bars),
                    bars=bars,
                )

        if last_error is not None:
            raise ProviderError(
                "Failed to load daily bars for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No daily bars found for symbol {symbol}.".format(symbol=canonical_symbol),
        )

    def get_stock_universe(self) -> UniverseResponse:
        """获取基础股票池。"""
        last_error = None

        for provider in self._iter_available_providers():
            try:
                items = provider.get_stock_universe()
            except ProviderError as exc:
                last_error = exc
                continue

            if items:
                return UniverseResponse(count=len(items), items=items)

        if last_error is not None:
            raise ProviderError("Failed to load stock universe from data providers.") from last_error

        raise DataNotFoundError("No stock universe data is currently available.")

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        """获取单只股票公告列表。"""
        if limit <= 0:
            raise InvalidRequestError("limit must be greater than 0.")

        canonical_symbol = normalize_symbol(symbol)
        normalized_start_date, normalized_end_date = _resolve_announcement_date_range(
            start_date=start_date,
            end_date=end_date,
        )
        last_error = None

        for provider in self._iter_available_providers():
            try:
                items = provider.get_stock_announcements(
                    canonical_symbol,
                    start_date=normalized_start_date,
                    end_date=normalized_end_date,
                    limit=limit,
                )
            except ProviderError as exc:
                last_error = exc
                continue

            if items:
                return AnnouncementListResponse(
                    symbol=canonical_symbol,
                    count=len(items),
                    items=items,
                )

        if last_error is not None:
            raise ProviderError(
                "Failed to load announcements for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No announcements found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        """获取单只股票基础财务摘要。"""
        canonical_symbol = normalize_symbol(symbol)
        last_error = None

        for provider in self._iter_available_providers():
            try:
                summary = provider.get_stock_financial_summary(canonical_symbol)
            except ProviderError as exc:
                last_error = exc
                continue

            if summary is not None:
                return summary

        if last_error is not None:
            raise ProviderError(
                "Failed to load financial summary for {symbol} from data providers.".format(
                    symbol=canonical_symbol,
                ),
            ) from last_error

        raise DataNotFoundError(
            "No financial summary found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def _iter_available_providers(self) -> list[MarketDataProvider]:
        """返回当前启用且可用的 provider 列表。"""
        available_providers = [
            provider for provider in self._providers if provider.is_available()
        ]
        if not available_providers:
            raise ProviderError("No enabled market data providers are available.")
        return available_providers


def _parse_optional_date(value: Optional[str], field_name: str) -> Optional[date]:
    """解析可选的 ISO 日期字符串。"""
    if value is None or value.strip() == "":
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InvalidDateError(
            "{field_name} must use YYYY-MM-DD format.".format(field_name=field_name),
        ) from exc


def _resolve_announcement_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[date, date]:
    """解析公告列表日期范围。"""
    normalized_start_date = _parse_optional_date(start_date, "start_date")
    normalized_end_date = _parse_optional_date(end_date, "end_date")

    if normalized_end_date is None:
        normalized_end_date = date.today()
    if normalized_start_date is None:
        normalized_start_date = normalized_end_date - timedelta(days=365)
    if normalized_start_date > normalized_end_date:
        raise InvalidDateError("start_date cannot be later than end_date.")

    return normalized_start_date, normalized_end_date
