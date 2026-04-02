"""A 股数据 service 层。"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta
import logging
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
from app.services.common.text_normalization import normalize_display_text
from app.services.data_service.cleaning.announcements import clean_announcements
from app.services.data_service.cleaning.bars import clean_daily_bars
from app.services.data_service.cleaning.financials import clean_financial_summary
from app.services.data_service.contracts.bars import DailyBarsCleaningSummary
from app.services.data_service.contracts.financials import FinancialSummaryCleaningSummary
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
from app.services.data_products.freshness import resolve_last_closed_trading_day

logger = logging.getLogger(__name__)
_BAR_PROVIDER_PRIORITY = ("mootdx", "baostock", "akshare")
_MOOTDX_VOLUME_MIGRATION_CURSOR = "migration:mootdx_volume_to_share:v1"


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
        self._preferred_unavailable_logged: set[tuple[str, tuple[str, ...]]] = set()
        self._run_local_migrations()

    def _run_local_migrations(self) -> None:
        if self._local_store is None:
            return
        self._ensure_mootdx_volume_migrated()

    def _ensure_mootdx_volume_migrated(self) -> None:
        if self._local_store is None:
            return
        if self._local_store.get_refresh_cursor(_MOOTDX_VOLUME_MIGRATION_CURSOR) == "done":
            return

        updated_rows = self._local_store.scale_daily_bar_volume_by_source(
            source="mootdx",
            factor=100.0,
        )
        self._local_store.set_refresh_cursor(_MOOTDX_VOLUME_MIGRATION_CURSOR, "done")
        logger.info(
            "market_data.migration.done name=mootdx_volume_to_share_v1 updated_rows=%s",
            updated_rows,
        )

    def get_stock_profile(self, symbol: str) -> StockProfile:
        canonical_symbol = normalize_symbol(symbol)
        logger.debug(
            "market_data.profile.start symbol=%s canonical_symbol=%s",
            symbol,
            canonical_symbol,
        )

        if self._local_store is not None:
            cached_profile = self._local_store.get_stock_profile(canonical_symbol)
            if cached_profile is not None:
                if _is_stock_profile_complete(cached_profile):
                    logger.debug(
                        "market_data.profile.cache_hit symbol=%s source=%s",
                        canonical_symbol,
                        cached_profile.source,
                    )
                    return cached_profile
                logger.debug(
                    "market_data.profile.cache_partial symbol=%s source=%s reason=incomplete_profile",
                    canonical_symbol,
                    cached_profile.source,
                )
                try:
                    profile = self._load_stock_profile_from_providers(canonical_symbol)
                except (ProviderError, DataNotFoundError):
                    logger.debug(
                        "market_data.profile.cache_partial_use symbol=%s source=%s reason=provider_unavailable",
                        canonical_symbol,
                        cached_profile.source,
                    )
                    return cached_profile

                merged_profile = _merge_stock_profiles(
                    cached_profile=cached_profile,
                    provider_profile=profile,
                )
                self._local_store.upsert_stock_profile(merged_profile)
                logger.debug(
                    "market_data.profile.cache_completed symbol=%s source=%s",
                    canonical_symbol,
                    merged_profile.source,
                )
                return merged_profile

        profile = self._load_stock_profile_from_providers(canonical_symbol)
        if self._local_store is not None:
            self._local_store.upsert_stock_profile(profile)
        logger.debug(
            "market_data.profile.done symbol=%s source=%s",
            canonical_symbol,
            profile.source,
        )
        return profile

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        *,
        force_refresh: bool = False,
        allow_remote_sync: bool = True,
        provider_names: Optional[Sequence[str]] = None,
    ) -> DailyBarResponse:
        canonical_symbol = normalize_symbol(symbol)
        logger.debug(
            "market_data.daily_bars.start symbol=%s canonical_symbol=%s start_date=%s end_date=%s",
            symbol,
            canonical_symbol,
            start_date,
            end_date,
        )
        request_uses_default_range = (
            (start_date is None or start_date.strip() == "")
            and (end_date is None or end_date.strip() == "")
        )
        normalized_start_date = _parse_optional_date(start_date, "start_date")
        normalized_end_date = _parse_optional_date(end_date, "end_date")
        if normalized_end_date is None:
            normalized_end_date = resolve_last_closed_trading_day()

        if (
            normalized_start_date is not None
            and normalized_end_date is not None
            and normalized_start_date > normalized_end_date
        ):
            raise InvalidDateError("start_date cannot be later than end_date.")

        if self._local_store is None:
            remote_result = self._load_daily_bars_from_providers(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                provider_names=provider_names,
            )
            logger.debug(
                "market_data.daily_bars.done symbol=%s count=%s source_mode=provider_only",
                canonical_symbol,
                len(remote_result.bars),
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                remote_result.bars,
                cleaning_summary=remote_result.cleaning_summary,
            )

        cached_bars = self._local_store.get_daily_bars(
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
        )

        if not allow_remote_sync:
            if cached_bars:
                logger.debug(
                    "market_data.daily_bars.skip_remote symbol=%s reason=allow_remote_sync_disabled_use_cache count=%s",
                    canonical_symbol,
                    len(cached_bars),
                )
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                    additional_warnings=["remote_sync_skipped_use_cache"],
                )
            logger.debug(
                "market_data.daily_bars.skip_remote symbol=%s reason=allow_remote_sync_disabled_no_cache",
                canonical_symbol,
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                [],
                additional_warnings=["remote_sync_skipped_no_cache"],
            )

        if (
            not force_refresh
            and
            normalized_start_date is not None
            and normalized_end_date is not None
            and self._local_store.is_range_covered(
                DATASET_DAILY_BARS,
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
            )
        ):
            logger.debug(
                "market_data.daily_bars.cache_hit symbol=%s start_date=%s end_date=%s count=%s",
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                len(cached_bars),
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                cached_bars,
            )

        sync_start_date = normalized_start_date
        sync_end_date = normalized_end_date

        if not force_refresh and sync_start_date is None and cached_bars:
            latest_local_trade_date = cached_bars[-1].trade_date
            sync_start_date = latest_local_trade_date + timedelta(days=1)
            sync_end_date = normalized_end_date
            if sync_start_date > sync_end_date:
                logger.debug(
                    "market_data.daily_bars.skip_remote symbol=%s reason=already_up_to_date",
                    canonical_symbol,
                )
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                )

        if (
            not force_refresh
            and sync_start_date is None
            and cached_bars
            and normalized_end_date is not None
        ):
            latest_local_trade_date = cached_bars[-1].trade_date
            if latest_local_trade_date < normalized_end_date:
                sync_start_date = latest_local_trade_date + timedelta(days=1)
                sync_end_date = normalized_end_date

        if force_refresh and sync_start_date is None:
            latest_local_trade_date = self._local_store.get_latest_daily_bar_date(
                canonical_symbol,
            )
            if latest_local_trade_date is not None:
                sync_start_date = latest_local_trade_date + timedelta(days=1)
            else:
                sync_start_date = normalized_start_date
            sync_end_date = normalized_end_date
            if (
                sync_start_date is not None
                and sync_end_date is not None
                and sync_start_date > sync_end_date
            ):
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                )

        try:
            remote_result = self._load_daily_bars_from_providers(
                canonical_symbol,
                sync_start_date,
                sync_end_date,
                provider_names=provider_names,
            )
        except ProviderError:
            if cached_bars and request_uses_default_range:
                logger.debug(
                    "market_data.daily_bars.remote_failed_use_cache symbol=%s cached_count=%s",
                    canonical_symbol,
                    len(cached_bars),
                )
                return _build_daily_bar_response(
                    canonical_symbol,
                    normalized_start_date,
                    normalized_end_date,
                    cached_bars,
                    additional_warnings=["remote_failed_use_cache"],
                )
            raise
        self._local_store.upsert_daily_bars(remote_result.bars)

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
            logger.debug(
                "market_data.daily_bars.done symbol=%s count=%s source_mode=local_plus_provider",
                canonical_symbol,
                len(merged_bars),
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                merged_bars,
                cleaning_summary=remote_result.cleaning_summary,
            )
        if cached_bars:
            logger.debug(
                "market_data.daily_bars.done symbol=%s count=%s source_mode=cache_fallback",
                canonical_symbol,
                len(cached_bars),
            )
            return _build_daily_bar_response(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                cached_bars,
                additional_warnings=["cache_fallback_use_existing_snapshot"],
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
        logger.debug(
            "market_data.intraday_bars.start symbol=%s canonical_symbol=%s frequency=%s start_datetime=%s end_datetime=%s limit=%s",
            symbol,
            canonical_symbol,
            frequency,
            start_datetime,
            end_datetime,
            limit,
        )
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
        logger.debug(
            "market_data.intraday_bars.done symbol=%s frequency=%s count=%s",
            canonical_symbol,
            normalized_frequency,
            len(bars),
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
        *,
        force_refresh: bool = False,
    ) -> AnnouncementListResponse:
        if limit <= 0:
            raise InvalidRequestError("limit must be greater than 0.")

        canonical_symbol = normalize_symbol(symbol)
        logger.debug(
            "market_data.announcements.start symbol=%s canonical_symbol=%s start_date=%s end_date=%s limit=%s",
            symbol,
            canonical_symbol,
            start_date,
            end_date,
            limit,
        )
        normalized_start_date, normalized_end_date = _resolve_announcement_date_range(
            start_date=start_date,
            end_date=end_date,
        )
        as_of_date = resolve_last_closed_trading_day()

        if (
            not force_refresh
            and self._local_store is not None
            and self._local_store.is_range_covered(
                DATASET_ANNOUNCEMENTS,
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
            )
        ):
            cached_items = self._local_store.get_stock_announcements(
                canonical_symbol,
                normalized_start_date,
                normalized_end_date,
                limit=limit,
            )
            if cached_items:
                cleaned_cached = clean_announcements(
                    symbol=canonical_symbol,
                    rows=cached_items,
                    as_of_date=as_of_date,
                    source_mode="local_cache",
                    freshness_mode="cache_preferred",
                )
                logger.debug(
                    "market_data.announcements.cache_hit symbol=%s count=%s",
                    canonical_symbol,
                    len(cleaned_cached.items),
                )
                return cleaned_cached.to_announcement_list_response()

        items = self._load_stock_announcements_from_providers(
            canonical_symbol,
            normalized_start_date,
            normalized_end_date,
            limit,
        )
        cleaned_remote = clean_announcements(
            symbol=canonical_symbol,
            rows=items,
            as_of_date=as_of_date,
            source_mode="provider_fetch",
            freshness_mode="force_refreshed" if force_refresh else "provider_fetch",
        )

        if self._local_store is not None:
            self._local_store.upsert_stock_announcements(
                cleaned_remote.to_announcement_items(),
            )
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
                cleaned_merged = clean_announcements(
                    symbol=canonical_symbol,
                    rows=merged_items,
                    as_of_date=as_of_date,
                    provider_used=cleaned_remote.provider_used,
                    fallback_applied=cleaned_remote.fallback_applied,
                    fallback_reason=cleaned_remote.fallback_reason,
                    source_mode="local_plus_provider",
                    freshness_mode="force_refreshed" if force_refresh else "provider_fetch",
                )
                logger.debug(
                    "market_data.announcements.done symbol=%s count=%s source_mode=local_plus_provider",
                    canonical_symbol,
                    len(cleaned_merged.items),
                )
                return cleaned_merged.to_announcement_list_response()

        if cleaned_remote.items:
            logger.debug(
                "market_data.announcements.done symbol=%s count=%s source_mode=provider_only",
                canonical_symbol,
                len(cleaned_remote.items),
            )
            return cleaned_remote.model_copy(
                update={
                    "source_mode": "provider_only",
                    "freshness_mode": "force_refreshed" if force_refresh else "provider_fetch",
                }
            ).to_announcement_list_response()

        raise DataNotFoundError(
            "No announcements found for symbol {symbol}.".format(
                symbol=canonical_symbol,
            ),
        )

    def _get_stock_financial_summary(
        self,
        symbol: str,
        *,
        force_refresh: bool,
    ) -> FinancialSummary:
        canonical_symbol = normalize_symbol(symbol)
        logger.debug(
            "market_data.financial_summary.start symbol=%s canonical_symbol=%s",
            symbol,
            canonical_symbol,
        )

        if not force_refresh and self._local_store is not None:
            cached_summary = self._local_store.get_stock_financial_summary(
                canonical_symbol,
            )
            if cached_summary is not None:
                cached_summary = _normalize_financial_summary_response(
                    cached_summary,
                    source_mode=cached_summary.source_mode or "local",
                    freshness_mode=cached_summary.freshness_mode or "cache_preferred",
                    provider_used=cached_summary.provider_used or cached_summary.source,
                    as_of_date=cached_summary.as_of_date or resolve_last_closed_trading_day(),
                )
                logger.debug(
                    "market_data.financial_summary.cache_hit symbol=%s source=%s",
                    canonical_symbol,
                    cached_summary.source,
                )
                return cached_summary

        fetched = self._load_stock_financial_summary_from_providers(canonical_symbol)
        cleaned = clean_financial_summary(
            symbol=canonical_symbol,
            rows=[fetched.summary],
            as_of_date=resolve_last_closed_trading_day(),
            default_source=fetched.provider_name,
            provider_used=fetched.provider_name,
            fallback_applied=False,
            fallback_reason=None,
            source_mode="provider_only",
            freshness_mode="force_refreshed" if force_refresh else "provider_fetch",
        )
        if cleaned.summary is None:
            raise DataNotFoundError(
                "No financial summary found for symbol {symbol}.".format(
                    symbol=canonical_symbol,
                ),
            )
        summary = _normalize_financial_summary_response(
            cleaned.summary.to_financial_summary(),
            cleaning_summary=cleaned.cleaning_summary,
            source_mode="provider_only",
            freshness_mode="force_refreshed" if force_refresh else "provider_fetch",
            provider_used=fetched.provider_name,
            as_of_date=cleaned.summary.as_of_date,
        )
        if self._local_store is not None:
            self._local_store.upsert_stock_financial_summary(summary)
        logger.debug(
            "market_data.financial_summary.done symbol=%s source=%s",
            canonical_symbol,
            summary.source,
        )
        return summary

    def get_stock_financial_summary(
        self,
        symbol: str,
        *,
        force_refresh: bool = False,
    ) -> FinancialSummary:
        return self._get_stock_financial_summary(symbol, force_refresh=force_refresh)

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
        sync_end_date = resolve_last_closed_trading_day()
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

        remote_result = self._load_daily_bars_from_providers(
            canonical_symbol,
            sync_start_date,
            sync_end_date,
        )

        if self._local_store is not None and remote_result.bars:
            self._local_store.upsert_daily_bars(remote_result.bars)
            latest_synced_trade_date = max(bar.trade_date for bar in remote_result.bars)
            if latest_synced_trade_date >= sync_start_date:
                self._local_store.mark_range_covered(
                    DATASET_DAILY_BARS,
                    canonical_symbol,
                    sync_start_date,
                    latest_synced_trade_date,
                )

        return len(remote_result.bars)

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
        return self._get_stock_financial_summary(symbol, force_refresh=True)

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
        *,
        provider_names: Optional[Sequence[str]] = None,
    ) -> "_DailyBarsFetchResult":
        providers = self._iter_available_providers(
            DAILY_BAR_CAPABILITY,
            provider_names=provider_names,
        )
        last_error = None
        provider_errors: list[str] = []

        for provider in providers:
            logger.debug(
                "market_data.daily_bars.provider_try symbol=%s provider=%s start_date=%s end_date=%s",
                symbol,
                provider.name,
                start_date,
                end_date,
            )
            try:
                bars = provider.get_daily_bars(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
            except ProviderError as exc:
                logger.debug(
                    "market_data.daily_bars.provider_fail symbol=%s provider=%s error=%s",
                    symbol,
                    provider.name,
                    exc,
                )
                last_error = exc
                provider_errors.append("{provider}: {message}".format(provider=provider.name, message=str(exc)))
                continue
            except Exception as exc:  # pragma: no cover
                last_error = ProviderError(
                    "{provider} failed to load daily bars.".format(provider=provider.name),
                )
                logger.debug(
                    "market_data.daily_bars.provider_fail symbol=%s provider=%s error_type=%s error=%s",
                    symbol,
                    provider.name,
                    type(exc).__name__,
                    exc,
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
                cleaned = clean_daily_bars(
                    symbol=symbol,
                    rows=bars,
                    as_of_date=end_date,
                    default_source=provider.name,
                )
                if cleaned.summary.warning_messages:
                    logger.debug(
                        "market_data.daily_bars.cleaning_warning symbol=%s provider=%s warnings=%s",
                        symbol,
                        provider.name,
                        cleaned.summary.warning_messages,
                    )
                if not cleaned.bars:
                    logger.debug(
                        "market_data.daily_bars.provider_fail symbol=%s provider=%s reason=cleaned_empty",
                        symbol,
                        provider.name,
                    )
                    provider_errors.append(
                        "{provider}: cleaned empty result".format(
                            provider=provider.name,
                        ),
                    )
                    continue
                logger.debug(
                    "market_data.daily_bars.fallback_use symbol=%s provider=%s count=%s",
                    symbol,
                    provider.name,
                    len(cleaned.bars),
                )
                return _DailyBarsFetchResult(
                    bars=cleaned.to_daily_bars(),
                    cleaning_summary=cleaned.summary,
                )
            logger.debug(
                "market_data.daily_bars.provider_fail symbol=%s provider=%s reason=empty_result",
                symbol,
                provider.name,
            )
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
        return _DailyBarsFetchResult(bars=[], cleaning_summary=None)

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

    def _load_stock_financial_summary_from_providers(
        self,
        symbol: str,
    ) -> "_FinancialSummaryFetchResult":
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
                return _FinancialSummaryFetchResult(
                    summary=summary,
                    provider_name=provider.name,
                )

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

    def _iter_available_providers(
        self,
        capability: str,
        provider_names: Sequence[str] | None = None,
    ) -> list[object]:
        providers = self._provider_registry.get_providers(capability, available_only=True)
        if not providers:
            logger.debug("market_data.providers.none capability=%s", capability)
            raise ProviderError(
                "No enabled market data providers are available for capability '{capability}'.".format(
                    capability=capability,
                ),
            )
        effective_provider_names: Sequence[str] | None = provider_names
        if effective_provider_names is None and capability in {
            DAILY_BAR_CAPABILITY,
            INTRADAY_BAR_CAPABILITY,
            TIMELINE_CAPABILITY,
        }:
            effective_provider_names = _BAR_PROVIDER_PRIORITY
        if effective_provider_names:
            preferred = {
                name: index for index, name in enumerate(effective_provider_names)
            }
            available_provider_names = {provider.name for provider in providers}
            preferred_missing = [
                name for name in effective_provider_names if name not in available_provider_names
            ]
            if preferred_missing:
                all_providers = self._provider_registry.get_providers(
                    capability,
                    available_only=False,
                )
                provider_reason_map = {
                    provider.name: provider.get_unavailable_reason()
                    for provider in all_providers
                }
                self._log_preferred_unavailable(
                    capability=capability,
                    preferred_missing=preferred_missing,
                    provider_reason_map=provider_reason_map,
                )
            providers = sorted(
                providers,
                key=lambda provider: preferred.get(
                    provider.name,
                    len(preferred) + 100,
                ),
            )
        logger.debug(
            "market_data.providers.selected capability=%s providers=%s",
            capability,
            [provider.name for provider in providers],
        )
        return providers

    def _log_preferred_unavailable(
        self,
        *,
        capability: str,
        preferred_missing: Sequence[str],
        provider_reason_map: dict[str, str | None],
    ) -> None:
        normalized_missing = tuple(sorted(preferred_missing))
        log_key = (capability, normalized_missing)
        if log_key in self._preferred_unavailable_logged:
            return
        self._preferred_unavailable_logged.add(log_key)
        missing_reasons = {
            name: provider_reason_map.get(name) for name in normalized_missing
        }
        logger.debug(
            "market_data.providers.preferred_unavailable capability=%s missing=%s reasons=%s",
            capability,
            list(normalized_missing),
            missing_reasons,
        )


def _build_daily_bar_response(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    bars: list[DailyBar],
    *,
    cleaning_summary: DailyBarsCleaningSummary | None = None,
    additional_warnings: Sequence[str] | None = None,
) -> DailyBarResponse:
    warning_messages: list[str] = []
    quality_status: str | None = None
    dropped_rows = 0
    dropped_duplicate_rows = 0
    if cleaning_summary is not None:
        warning_messages = list(cleaning_summary.warning_messages)
        quality_status = cleaning_summary.quality_status
        dropped_rows = cleaning_summary.dropped_rows
        dropped_duplicate_rows = cleaning_summary.dropped_duplicate_rows
    elif bars:
        quality_status = "ok"
    if additional_warnings:
        warning_messages.extend(item for item in additional_warnings if item)
    warning_messages = list(dict.fromkeys(warning_messages))
    if quality_status is None and bars:
        quality_status = "ok"
    return DailyBarResponse(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        count=len(bars),
        bars=bars,
        quality_status=quality_status,
        cleaning_warnings=warning_messages,
        dropped_rows=dropped_rows,
        dropped_duplicate_rows=dropped_duplicate_rows,
    )


@dataclass(frozen=True)
class _DailyBarsFetchResult:
    bars: list[DailyBar]
    cleaning_summary: DailyBarsCleaningSummary | None


@dataclass(frozen=True)
class _FinancialSummaryFetchResult:
    summary: FinancialSummary
    provider_name: str


def _normalize_financial_summary_response(
    summary: FinancialSummary,
    *,
    cleaning_summary: FinancialSummaryCleaningSummary | None = None,
    source_mode: str | None = None,
    freshness_mode: str | None = None,
    provider_used: str | None = None,
    as_of_date: date | None = None,
) -> FinancialSummary:
    normalized_warnings = list(summary.cleaning_warnings)
    normalized_missing_fields = list(summary.missing_fields)
    normalized_coerced_fields = list(summary.coerced_fields)
    quality_status: str | None = summary.quality_status
    report_type = summary.report_type
    normalized_name = normalize_display_text(summary.name) or summary.name
    if cleaning_summary is not None:
        normalized_warnings.extend(cleaning_summary.warning_messages)
        normalized_missing_fields.extend(cleaning_summary.missing_fields)
        normalized_coerced_fields.extend(cleaning_summary.coerced_fields)
        if quality_status is None:
            quality_status = cleaning_summary.quality_status

    if report_type is None and summary.report_period is not None:
        inferred_report_type = _infer_financial_report_type_from_period(summary.report_period)
        if inferred_report_type is not None:
            report_type = inferred_report_type
        else:
            normalized_warnings.append("unknown_report_type_from_report_period")

    recomputed_missing_fields = _recompute_financial_missing_fields(summary)
    if recomputed_missing_fields:
        normalized_missing_fields.extend(recomputed_missing_fields)

    deduped_warnings = list(dict.fromkeys(item for item in normalized_warnings if item))
    deduped_missing_fields = list(
        dict.fromkeys(item for item in normalized_missing_fields if item),
    )
    deduped_coerced_fields = list(
        dict.fromkeys(item for item in normalized_coerced_fields if item),
    )

    quality_status = _resolve_financial_quality_status(
        summary=summary,
        existing_status=quality_status,
        missing_fields=deduped_missing_fields,
        warning_messages=deduped_warnings,
    )

    return summary.model_copy(
        update={
            "name": normalized_name,
            "report_type": report_type,
            "quality_status": quality_status,
            "cleaning_warnings": deduped_warnings,
            "missing_fields": deduped_missing_fields,
            "coerced_fields": deduped_coerced_fields,
            "provider_used": provider_used or summary.provider_used or summary.source,
            "source_mode": source_mode or summary.source_mode,
            "freshness_mode": freshness_mode or summary.freshness_mode,
            "as_of_date": as_of_date or summary.as_of_date or resolve_last_closed_trading_day(),
        }
    )


def _infer_financial_report_type_from_period(report_period: date) -> str | None:
    if report_period.month == 3 and report_period.day == 31:
        return "q1"
    if report_period.month == 6 and report_period.day == 30:
        return "half"
    if report_period.month == 9 and report_period.day == 30:
        return "q3"
    if report_period.month == 12 and report_period.day == 31:
        return "annual"
    return None


def _recompute_financial_missing_fields(summary: FinancialSummary) -> list[str]:
    candidate_fields = (
        "revenue",
        "revenue_yoy",
        "net_profit",
        "net_profit_yoy",
        "roe",
        "gross_margin",
        "debt_ratio",
        "eps",
        "bps",
    )
    missing: list[str] = []
    for field_name in candidate_fields:
        value = getattr(summary, field_name)
        if value is None:
            missing.append(field_name)
    return missing


def _resolve_financial_quality_status(
    *,
    summary: FinancialSummary,
    existing_status: str | None,
    missing_fields: list[str],
    warning_messages: list[str],
) -> str:
    key_missing_fields = {
        "revenue",
        "revenue_yoy",
        "net_profit",
        "net_profit_yoy",
        "roe",
    }
    missing_set = set(missing_fields)
    key_missing_count = len(key_missing_fields & missing_set)
    total_missing_count = len(missing_set)
    secondary_fields = ("gross_margin", "debt_ratio", "eps", "bps")
    secondary_available_count = sum(
        1 for field_name in secondary_fields if getattr(summary, field_name) is not None
    )
    has_any_value = any(
        getattr(summary, field_name) is not None
        for field_name in (
            "revenue",
            "revenue_yoy",
            "net_profit",
            "net_profit_yoy",
            "roe",
            "gross_margin",
            "debt_ratio",
            "eps",
            "bps",
        )
    )
    has_warning = bool(warning_messages)

    inferred_status = "ok"
    if not has_any_value:
        inferred_status = "degraded"
        if summary.report_period is None and summary.report_type in {None, "unknown"}:
            inferred_status = "failed"
    elif key_missing_count >= 5 or total_missing_count >= 6:
        if secondary_available_count >= 3 and summary.report_period is not None:
            inferred_status = "warning"
            warning_messages.append("core_financial_fields_missing_use_secondary_metrics")
        else:
            inferred_status = "degraded"
    elif key_missing_count > 0 or total_missing_count > 0 or has_warning:
        inferred_status = "warning"

    if existing_status is None:
        return inferred_status
    if existing_status == "failed":
        return existing_status
    if (
        existing_status == "degraded"
        and inferred_status == "warning"
        and "core_financial_fields_missing_use_secondary_metrics" in warning_messages
    ):
        return "warning"
    if inferred_status == "failed":
        return "degraded"
    if existing_status == "degraded" or inferred_status == "degraded":
        return "degraded"
    if existing_status == "warning" or inferred_status == "warning":
        return "warning"
    return "ok"


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


def _is_stock_profile_complete(profile: StockProfile) -> bool:
    return all(
        [
            profile.industry is not None,
            profile.list_date is not None,
            profile.total_market_cap is not None,
            profile.circulating_market_cap is not None,
        ]
    )


def _merge_stock_profiles(
    *,
    cached_profile: StockProfile,
    provider_profile: StockProfile,
) -> StockProfile:
    return StockProfile(
        symbol=provider_profile.symbol,
        code=provider_profile.code or cached_profile.code,
        exchange=provider_profile.exchange,
        name=provider_profile.name or cached_profile.name,
        industry=provider_profile.industry or cached_profile.industry,
        list_date=provider_profile.list_date or cached_profile.list_date,
        status=provider_profile.status or cached_profile.status,
        total_market_cap=(
            provider_profile.total_market_cap
            if provider_profile.total_market_cap is not None
            else cached_profile.total_market_cap
        ),
        circulating_market_cap=(
            provider_profile.circulating_market_cap
            if provider_profile.circulating_market_cap is not None
            else cached_profile.circulating_market_cap
        ),
        source=provider_profile.source or cached_profile.source,
    )
