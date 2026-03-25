"""A 股数据 service 层。"""

from __future__ import annotations

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
    IntradayBar,
    IntradayBarResponse,
    StockProfile,
    TimelinePoint,
    TimelineResponse,
    UniverseItem,
    UniverseResponse,
)
from app.schemas.provider import ProviderCapabilityReport, ProviderHealthReport
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
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.base import (
    ANNOUNCEMENT_CAPABILITY,
    DAILY_BAR_CAPABILITY,
    FINANCIAL_SUMMARY_CAPABILITY,
    INTRADAY_BAR_CAPABILITY,
    PROFILE_CAPABILITY,
    TIMELINE_CAPABILITY,
    UNIVERSE_CAPABILITY,
)


class MarketDataService:
    """统一封装 A 股数据访问、本地落盘与 provider 选择。"""

    def __init__(
        self,
        providers: Sequence[object] | ProviderRegistry,
        local_store: Optional[LocalMarketDataStore] = None,
    ) -> None:
        if isinstance(providers, ProviderRegistry):
            self._provider_registry = providers
        else:
            self._provider_registry = ProviderRegistry(providers)
        self._local_store = local_store

    def get_stock_profile(self, symbol: str) -> StockProfile:
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

        try:
            remote_bars = self._load_daily_bars_from_providers(
                canonical_symbol,
                sync_start_date,
                sync_end_date,
            )
        except ProviderError:
            if cached_bars and normalized_start_date is None and normalized_end_date is None:
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                )
            raise
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

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> IntradayBarResponse:
        canonical_symbol = normalize_symbol(symbol)
        normalized_frequency = _normalize_intraday_frequency(frequency)
        normalized_start_datetime = _parse_optional_datetime(
            start_datetime,
            "start_datetime",
        )
        normalized_end_datetime = _parse_optional_datetime(
            end_datetime,
            "end_datetime",
        )

        if (
            normalized_start_datetime is not None
            and normalized_end_datetime is not None
            and normalized_start_datetime > normalized_end_datetime
        ):
            raise InvalidDateError(
                "start_datetime cannot be later than end_datetime.",
            )

        bars = self._load_intraday_bars_from_providers(
            canonical_symbol,
            frequency=normalized_frequency,
            start_datetime=normalized_start_datetime,
            end_datetime=normalized_end_datetime,
            limit=limit,
        )
        if not bars:
            raise DataNotFoundError(
                "No intraday bars found for symbol {symbol}.".format(
                    symbol=canonical_symbol,
                ),
            )
        return IntradayBarResponse(
            symbol=canonical_symbol,
            frequency=normalized_frequency,
            start_datetime=normalized_start_datetime,
            end_datetime=normalized_end_datetime,
            count=len(bars),
            bars=bars,
        )

    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> TimelineResponse:
        canonical_symbol = normalize_symbol(symbol)
        points = self._load_timeline_from_providers(
            canonical_symbol,
            limit=limit,
        )
        if not points:
            raise DataNotFoundError(
                "No timeline data found for symbol {symbol}.".format(
                    symbol=canonical_symbol,
                ),
            )
        return TimelineResponse(
            symbol=canonical_symbol,
            count=len(points),
            points=points,
        )

    def get_stock_universe(self) -> UniverseResponse:
        if self._local_store is not None:
            cached_items = self._local_store.get_stock_universe()
            if cached_items:
                return UniverseResponse(count=len(cached_items), items=cached_items)

        items = self._load_stock_universe_from_providers()
        if self._local_store is not None:
            self._local_store.replace_stock_universe(items)
        return UniverseResponse(count=len(items), items=items)

    def refresh_stock_universe(self) -> UniverseResponse:
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
        canonical_symbol = normalize_symbol(symbol)
        profile = self._load_stock_profile_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_profile(profile)
        return profile

    def refresh_daily_bars(self, symbol: str, lookback_days: int = 400) -> int:
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
                    return 0
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
        if self._local_store is None:
            return None
        return self._local_store.get_refresh_cursor(cursor_key)

    def set_refresh_cursor(self, cursor_key: str, cursor_value: Optional[str]) -> None:
        if self._local_store is None:
            return
        self._local_store.set_refresh_cursor(cursor_key, cursor_value)

    def refresh_stock_announcements(
        self,
        symbol: str,
        lookback_days: int = 90,
        limit: int = 2000,
    ) -> int:
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
        canonical_symbol = normalize_symbol(symbol)
        summary = self._load_stock_financial_summary_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_financial_summary(summary)
        return summary

    def get_provider_capability_reports(self) -> list[ProviderCapabilityReport]:
        return self._provider_registry.get_capability_reports()

    def get_provider_health_reports(self) -> list[ProviderHealthReport]:
        return self._provider_registry.get_health_reports()

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        with ExitStack() as stack:
            for provider in self._provider_registry.get_all_available_providers():
                session_scope = getattr(provider, "session_scope", None)
                if callable(session_scope):
                    stack.enter_context(session_scope())
            yield

    def _load_stock_profile_from_providers(self, symbol: str) -> StockProfile:
        providers = self._iter_available_providers(PROFILE_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                profile = provider.get_stock_profile(symbol)
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load stock profile.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if profile is not None:
                return profile

        if last_error is not None:
            raise ProviderError(
                "Failed to load stock profile for {symbol} from data providers. Details: {details}".format(
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
        providers = self._iter_available_providers(DAILY_BAR_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                bars = provider.get_daily_bars(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load daily bars.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if bars:
                return bars
            provider_errors.append(
                "{provider}: empty result".format(provider=provider.name),
            )

        if last_error is not None:
            raise ProviderError(
                "Failed to load daily bars for {symbol} from data providers. Details: {details}".format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error
        return []

    def _load_intraday_bars_from_providers(
        self,
        symbol: str,
        frequency: str,
        start_datetime: Optional[datetime],
        end_datetime: Optional[datetime],
        limit: Optional[int],
    ) -> list[IntradayBar]:
        providers = self._iter_available_providers(INTRADAY_BAR_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                bars = provider.get_intraday_bars(
                    symbol,
                    frequency=frequency,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    limit=limit,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load intraday bars.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if bars:
                return bars

        if last_error is not None:
            raise ProviderError(
                "Failed to load intraday bars for {symbol} from data providers. Details: {details}".format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error
        return []

    def _load_timeline_from_providers(
        self,
        symbol: str,
        limit: Optional[int],
    ) -> list[TimelinePoint]:
        providers = self._iter_available_providers(TIMELINE_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                points = provider.get_timeline(
                    symbol,
                    limit=limit,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load timeline.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if points:
                return points

        if last_error is not None:
            raise ProviderError(
                "Failed to load timeline for {symbol} from data providers. Details: {details}".format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error
        return []

    def _load_stock_universe_from_providers(self) -> list[UniverseItem]:
        providers = self._iter_available_providers(UNIVERSE_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                items = provider.get_stock_universe()
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load stock universe.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if items:
                return items

        if last_error is not None:
            raise ProviderError(
                "Failed to load stock universe from data providers. Details: {details}".format(
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
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
        providers = self._iter_available_providers(ANNOUNCEMENT_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                items = provider.get_stock_announcements(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load announcements.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if items:
                return items

        if last_error is not None:
            raise ProviderError(
                "Failed to load announcements for {symbol} from data providers. Details: {details}".format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error
        return []

    def _load_stock_financial_summary_from_providers(self, symbol: str) -> FinancialSummary:
        providers = self._iter_available_providers(FINANCIAL_SUMMARY_CAPABILITY)
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            try:
                summary = provider.get_stock_financial_summary(symbol)
            except ProviderError as exc:
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load financial summary.".format(provider=provider.name),
                )
                provider_errors.append(
                    "{provider}: {error_type}: {message}".format(
                        provider=provider.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue
            if summary is not None:
                return summary

        if last_error is not None:
            raise ProviderError(
                "Failed to load financial summary for {symbol} from data providers. Details: {details}".format(
                    symbol=symbol,
                    details=" | ".join(provider_errors) if provider_errors else str(last_error),
                ),
            ) from last_error
        raise DataNotFoundError(
            "No financial summary found for symbol {symbol}.".format(symbol=symbol),
        )

    def _iter_available_providers(self, capability: str) -> list[object]:
        providers = self._provider_registry.get_providers(capability, available_only=True)
        if not providers:
            raise ProviderError(
                "No enabled market data providers are available for capability '{capability}'.".format(
                    capability=capability,
                ),
            )
        return providers


def _build_daily_bar_response(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    bars: list[DailyBar],
) -> DailyBarResponse:
    return DailyBarResponse(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        count=len(bars),
        bars=bars,
    )


def _parse_optional_date(value: Optional[str], field_name: str) -> Optional[date]:
    if value is None or value.strip() == "":
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InvalidDateError(
            "{field_name} must use YYYY-MM-DD format.".format(field_name=field_name),
        ) from exc


def _parse_optional_datetime(
    value: Optional[str],
    field_name: str,
) -> Optional[datetime]:
    if value is None or value.strip() == "":
        return None

    text = value.strip()
    datetime_patterns = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    )
    for pattern in datetime_patterns:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue

    raise InvalidDateError(
        "{field_name} must use YYYY-MM-DDTHH:MM[:SS] format.".format(
            field_name=field_name,
        ),
    )


def _normalize_intraday_frequency(frequency: str) -> str:
    cleaned = frequency.strip().lower()
    if cleaned in {"1m", "5m"}:
        return cleaned
    raise InvalidRequestError(
        "Unsupported intraday frequency '{frequency}'. Supported values: 1m, 5m.".format(
            frequency=frequency,
        ),
    )


def _resolve_announcement_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[date, date]:
    normalized_start_date = _parse_optional_date(start_date, "start_date")
    normalized_end_date = _parse_optional_date(end_date, "end_date")

    if normalized_end_date is None:
        normalized_end_date = date.today()
    if normalized_start_date is None:
        normalized_start_date = normalized_end_date - timedelta(days=365)
    if normalized_start_date > normalized_end_date:
        raise InvalidDateError("start_date cannot be later than end_date.")

    return normalized_start_date, normalized_end_date
