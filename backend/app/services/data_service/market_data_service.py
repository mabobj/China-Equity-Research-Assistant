"""A 股数据 service 层。"""

from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta
from typing import Iterator, Optional, Sequence

from app.db.market_data_store import (
    DATASET_ANNOUNCEMENTS,
    DATASET_DAILY_BARS,
    LocalMarketDataStore,
)
from app.schemas.market_data import (
    DailyBar,
    DailyBarResponse,
    StockProfile,
    UniverseItem,
    UniverseResponse,
)
from app.schemas.research_inputs import (
    AnnouncementItem,
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
    """统一封装 A 股数据访问、本地落盘与简单 fallback。"""

    def __init__(
        self,
        providers: Sequence[MarketDataProvider],
        local_store: Optional[LocalMarketDataStore] = None,
    ) -> None:
        self._providers = list(providers)
        self._local_store = local_store

    def get_stock_profile(self, symbol: str) -> StockProfile:
        """获取单只股票基础信息。"""
        canonical_symbol = normalize_symbol(symbol)

        if self._local_store is not None:
            cached_profile = self._local_store.get_stock_profile(canonical_symbol)
            if cached_profile is not None:
                return cached_profile

        profile = self._load_stock_profile_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_profile(profile)
        return profile

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

        if self._local_store is None:
            bars = self._load_daily_bars_from_providers(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                bars,
            )

        cached_bars = self._local_store.get_daily_bars(
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
        )

        if (
            normalized_start_date is not None
            and normalized_end_date is not None
            and self._local_store.is_range_covered(
                DATASET_DAILY_BARS,
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
            )
        ):
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                cached_bars,
            )

        sync_start_date = normalized_start_date
        sync_end_date = normalized_end_date

        if sync_start_date is None and cached_bars:
            latest_local_trade_date = cached_bars[-1].trade_date
            sync_start_date = latest_local_trade_date + timedelta(days=1)
            sync_end_date = normalized_end_date or date.today()
            if sync_start_date > sync_end_date:
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                )

        remote_bars = self._load_daily_bars_from_providers(
            canonical_symbol,
            sync_start_date,
            sync_end_date,
        )
        self._local_store.upsert_daily_bars(remote_bars)

        if sync_start_date is not None and sync_end_date is not None:
            self._local_store.mark_range_covered(
                DATASET_DAILY_BARS,
                canonical_symbol,
                sync_start_date,
                sync_end_date,
            )

        merged_bars = self._local_store.get_daily_bars(
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
        )
        if merged_bars:
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                merged_bars,
            )

        if cached_bars:
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                cached_bars,
            )

        raise DataNotFoundError(
            "No daily bars found for symbol {symbol}.".format(symbol=canonical_symbol),
        )

    def get_stock_universe(self) -> UniverseResponse:
        """获取基础股票池。"""
        if self._local_store is not None:
            cached_items = self._local_store.get_stock_universe()
            if cached_items:
                return UniverseResponse(count=len(cached_items), items=cached_items)

        items = self._load_stock_universe_from_providers()
        if self._local_store is not None:
            self._local_store.replace_stock_universe(items)
        return UniverseResponse(count=len(items), items=items)

    def refresh_stock_universe(self) -> UniverseResponse:
        """强制从线上刷新股票池，并回写本地存储。"""
        items = self._load_stock_universe_from_providers()
        if self._local_store is not None:
            self._local_store.replace_stock_universe(items)
        return UniverseResponse(count=len(items), items=items)

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

        if self._local_store is not None and self._local_store.is_range_covered(
            DATASET_ANNOUNCEMENTS,
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
        ):
            cached_items = self._local_store.get_stock_announcements(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                limit=limit,
            )
            if cached_items:
                return AnnouncementListResponse(
                    symbol=canonical_symbol,
                    count=len(cached_items),
                    items=cached_items,
                )

        items = self._load_stock_announcements_from_providers(
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
            limit,
        )

        if self._local_store is not None:
            self._local_store.upsert_stock_announcements(items)
            self._local_store.mark_range_covered(
                DATASET_ANNOUNCEMENTS,
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
            )
            merged_items = self._local_store.get_stock_announcements(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                limit=limit,
            )
            if merged_items:
                return AnnouncementListResponse(
                    symbol=canonical_symbol,
                    count=len(merged_items),
                    items=merged_items,
                )

        if items:
            return AnnouncementListResponse(
                symbol=canonical_symbol,
                count=len(items),
                items=items,
            )

        raise DataNotFoundError(
            "No announcements found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        """获取单只股票基础财务摘要。"""
        canonical_symbol = normalize_symbol(symbol)

        if self._local_store is not None:
            cached_summary = self._local_store.get_stock_financial_summary(
                canonical_symbol,
            )
            if cached_summary is not None:
                return cached_summary

        summary = self._load_stock_financial_summary_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_financial_summary(summary)
        return summary

    def refresh_stock_profile(self, symbol: str) -> StockProfile:
        """强制从线上刷新股票基础信息。"""
        canonical_symbol = normalize_symbol(symbol)
        profile = self._load_stock_profile_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_profile(profile)
        return profile

    def refresh_daily_bars(self, symbol: str, lookback_days: int = 400) -> int:
        """强制从线上补齐近期日线，并回写本地存储。"""
        if lookback_days <= 0:
            raise InvalidRequestError("lookback_days must be greater than 0.")

        canonical_symbol = normalize_symbol(symbol)
        sync_end_date = date.today()
        sync_start_date = sync_end_date - timedelta(days=lookback_days - 1)

        if self._local_store is not None:
            latest_local_trade_date = self._local_store.get_latest_daily_bar_date(
                canonical_symbol,
            )
            if latest_local_trade_date is not None:
                if latest_local_trade_date >= sync_end_date:
                    # 今日数据已经在本地，直接跳过本次增量请求。
                    return 0
                # 已有本地日线后，增量补全查询“本地最新下一天”到今日。
                sync_start_date = latest_local_trade_date + timedelta(days=1)

        if sync_start_date > sync_end_date:
            return 0

        remote_bars = self._load_daily_bars_from_providers(
            canonical_symbol,
            sync_start_date,
            sync_end_date,
        )

        if self._local_store is not None and remote_bars:
            self._local_store.upsert_daily_bars(remote_bars)
            latest_synced_trade_date = max(bar.trade_date for bar in remote_bars)
            if latest_synced_trade_date >= sync_start_date:
                self._local_store.mark_range_covered(
                    DATASET_DAILY_BARS,
                    canonical_symbol,
                    sync_start_date,
                    latest_synced_trade_date,
                )

        return len(remote_bars)

    def get_refresh_cursor(self, cursor_key: str) -> Optional[str]:
        """读取本地补全游标。"""
        if self._local_store is None:
            return None
        return self._local_store.get_refresh_cursor(cursor_key)

    def set_refresh_cursor(self, cursor_key: str, cursor_value: Optional[str]) -> None:
        """写入本地补全游标。"""
        if self._local_store is None:
            return
        self._local_store.set_refresh_cursor(cursor_key, cursor_value)

    def refresh_stock_announcements(
        self,
        symbol: str,
        lookback_days: int = 90,
        limit: int = 2000,
    ) -> int:
        """强制从线上增量刷新近期公告，并回写本地存储。"""
        if lookback_days <= 0:
            raise InvalidRequestError("lookback_days must be greater than 0.")
        if limit <= 0:
            raise InvalidRequestError("limit must be greater than 0.")

        canonical_symbol = normalize_symbol(symbol)
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days - 1)
        if self._local_store is not None:
            latest_publish_date = self._local_store.get_latest_announcement_publish_date(
                canonical_symbol,
            )
            if latest_publish_date is not None:
                # 往前回补 3 天，兼容公告延迟发布和数据修订。
                start_date = max(start_date, latest_publish_date - timedelta(days=3))

        items = self._load_stock_announcements_from_providers(
            canonical_symbol,
            start_date,
            end_date,
            limit,
        )

        if self._local_store is not None:
            self._local_store.upsert_stock_announcements(items)
            if items:
                self._local_store.mark_range_covered(
                    DATASET_ANNOUNCEMENTS,
                    canonical_symbol,
                    start_date,
                    max(item.publish_date for item in items),
                )
            else:
                self._local_store.mark_range_covered(
                    DATASET_ANNOUNCEMENTS,
                    canonical_symbol,
                    start_date,
                    end_date,
                )

        return len(items)

    def refresh_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        """强制从线上刷新基础财务摘要。"""
        canonical_symbol = normalize_symbol(symbol)
        summary = self._load_stock_financial_summary_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_financial_summary(summary)
        return summary

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        """在一次批量流程里复用 provider 会话。"""
        with ExitStack() as stack:
            for provider in self._iter_available_providers():
                session_scope = getattr(provider, "session_scope", None)
                if callable(session_scope):
                    stack.enter_context(session_scope())
            yield

    def _load_stock_profile_from_providers(self, symbol: str) -> StockProfile:
        """从 provider 加载股票基础信息。"""
        last_error = None
        provider_errors: list[str] = []

        for provider in self._iter_available_providers():
            provider_name = getattr(provider, "name", "provider")
            try:
                profile = provider.get_stock_profile(symbol)
            except ProviderError as exc:
                last_error = exc
                provider_errors.append(
                    "{provider}: {message}".format(
                        provider=provider_name,
                        message=str(exc),
                    ),
                )
                continue
            except Exception as exc:  # pragma: no cover - 兜底保护
                last_error = ProviderError(
                    "{provider} failed to load stock profile.".format(
                        provider=provider_name,
                    ),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider_name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )
                continue

            if profile is not None:
                return profile

        if last_error is not None:
            raise ProviderError(
                (
                    "Failed to load stock profile for {symbol} from data providers. "
                    "Details: {details}"
                ).format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error

        raise DataNotFoundError(
            "No stock profile found for symbol {symbol}.".format(symbol=symbol),
        )

    def _load_daily_bars_from_providers(
        self,
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> list[DailyBar]:
        """从 provider 加载日线数据。"""
        last_error = None
        provider_errors: list[str] = []

        for provider in self._iter_available_providers():
            provider_name = getattr(provider, "name", "provider")
            try:
                bars = provider.get_daily_bars(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append(
                    "{provider}: {message}".format(
                        provider=provider_name,
                        message=str(exc),
                    ),
                )
                continue
            except Exception as exc:  # pragma: no cover - 兜底保护
                last_error = ProviderError(
                    "{provider} failed to load daily bars.".format(
                        provider=provider_name,
                    ),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider_name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )
                continue

            if bars:
                return bars

        if last_error is not None:
            raise ProviderError(
                (
                    "Failed to load daily bars for {symbol} from data providers. "
                    "Details: {details}"
                ).format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error

        return []

    def _load_stock_universe_from_providers(self) -> list[UniverseItem]:
        """从 provider 加载股票池。"""
        last_error = None
        provider_errors: list[str] = []

        for provider in self._iter_available_providers():
            provider_name = getattr(provider, "name", "provider")
            try:
                items = provider.get_stock_universe()
            except ProviderError as exc:
                last_error = exc
                provider_errors.append(
                    "{provider}: {message}".format(
                        provider=provider_name,
                        message=str(exc),
                    ),
                )
                continue
            except Exception as exc:  # pragma: no cover - 兜底保护
                last_error = ProviderError(
                    "{provider} failed to load stock universe.".format(
                        provider=provider_name,
                    ),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider_name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )
                continue

            if items:
                return items

        if last_error is not None:
            raise ProviderError(
                "Failed to load stock universe from data providers. Details: {details}".format(
                    details=" | ".join(provider_errors)
                    if provider_errors
                    else str(last_error),
                ),
            ) from last_error

        raise DataNotFoundError("No stock universe data is currently available.")

    def _load_stock_announcements_from_providers(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> list[AnnouncementItem]:
        """从 provider 加载公告列表。"""
        last_error = None
        provider_errors: list[str] = []

        for provider in self._iter_available_providers():
            provider_name = getattr(provider, "name", "provider")
            try:
                items = provider.get_stock_announcements(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append(
                    "{provider}: {message}".format(
                        provider=provider_name,
                        message=str(exc),
                    ),
                )
                continue
            except Exception as exc:  # pragma: no cover - 兜底保护
                last_error = ProviderError(
                    "{provider} failed to load announcements.".format(
                        provider=provider_name,
                    ),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider_name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )
                continue

            if items:
                return items

        if last_error is not None:
            raise ProviderError(
                (
                    "Failed to load announcements for {symbol} from data providers. "
                    "Details: {details}"
                ).format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error

        return []

    def _load_stock_financial_summary_from_providers(self, symbol: str) -> FinancialSummary:
        """从 provider 加载财务摘要。"""
        last_error = None
        provider_errors: list[str] = []

        for provider in self._iter_available_providers():
            provider_name = getattr(provider, "name", "provider")
            try:
                summary = provider.get_stock_financial_summary(symbol)
            except ProviderError as exc:
                last_error = exc
                provider_errors.append(
                    "{provider}: {message}".format(
                        provider=provider_name,
                        message=str(exc),
                    ),
                )
                continue
            except Exception as exc:  # pragma: no cover - 兜底保护
                last_error = ProviderError(
                    "{provider} failed to load financial summary.".format(
                        provider=provider_name,
                    ),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider_name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    ),
                )
                continue

            if summary is not None:
                return summary

        if last_error is not None:
            raise ProviderError(
                (
                    "Failed to load financial summary for {symbol} from data providers. "
                    "Details: {details}"
                ).format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error

        raise DataNotFoundError(
            "No financial summary found for symbol {symbol}.".format(symbol=symbol),
        )

    def _iter_available_providers(self) -> list[MarketDataProvider]:
        """返回当前启用且可用的 provider 列表。"""
        available_providers = [
            provider for provider in self._providers if provider.is_available()
        ]
        if not available_providers:
            raise ProviderError("No enabled market data providers are available.")
        return available_providers


def _build_daily_bar_response(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    bars: list[DailyBar],
) -> DailyBarResponse:
    """构造统一的日线响应。"""
    return DailyBarResponse(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        count=len(bars),
        bars=bars,
    )


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
