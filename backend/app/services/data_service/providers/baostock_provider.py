"""BaoStock provider for basic A-share market data and financial fallback."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import importlib
import importlib.util
import math
from threading import RLock
from typing import Any, Iterator, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    parse_symbol,
)
from app.services.data_service.providers.base import (
    DAILY_BAR_CAPABILITY,
    FINANCIAL_SUMMARY_CAPABILITY,
    PROFILE_CAPABILITY,
    UNIVERSE_CAPABILITY,
)

_BAOSTOCK_LOCK = RLock()


class BaostockProvider:
    """BaoStock provider."""

    name = "baostock"
    capabilities = (
        PROFILE_CAPABILITY,
        DAILY_BAR_CAPABILITY,
        FINANCIAL_SUMMARY_CAPABILITY,
        UNIVERSE_CAPABILITY,
    )

    def __init__(self) -> None:
        self._session_depth = 0
        self._logged_in_module: Optional[Any] = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("baostock") is not None

    def get_unavailable_reason(self) -> Optional[str]:
        if self.is_available():
            return None
        return "BaoStock is not installed or unavailable."

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        self._ensure_available()
        bs = _get_baostock_module()

        with _BAOSTOCK_LOCK:
            should_login = self._session_depth == 0
            if should_login:
                _login_baostock(bs)
                self._logged_in_module = bs
            self._session_depth += 1

            try:
                yield
            finally:
                self._session_depth -= 1
                if self._session_depth == 0:
                    try:
                        if self._logged_in_module is not None:
                            self._logged_in_module.logout()
                    finally:
                        self._logged_in_module = None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        self._ensure_available()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with self.session_scope():
                bs = self._get_active_module()
                rows = _result_to_rows(bs.query_stock_basic(code=baostock_symbol))
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load stock profile.") from exc

        if not rows:
            return None

        row = rows[0]
        return StockProfile(
            symbol=parts.canonical,
            code=parts.code,
            exchange=parts.exchange,
            name=_as_optional_string(row.get("code_name")) or parts.code,
            industry=None,
            list_date=_parse_iso_date(row.get("ipoDate")),
            status=_map_trade_status(row.get("status")),
            total_market_cap=None,
            circulating_market_cap=None,
            source=self.name,
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        adjustment_mode: str = "raw",
    ) -> list[DailyBar]:
        self._ensure_available()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with self.session_scope():
                bs = self._get_active_module()
                rows = _result_to_rows(
                    bs.query_history_k_data_plus(
                        code=baostock_symbol,
                        fields="date,open,high,low,close,volume,amount",
                        start_date=_format_baostock_date(start_date),
                        end_date=_format_baostock_date(end_date),
                        frequency="d",
                        adjustflag=_format_baostock_adjustflag(adjustment_mode),
                    )
                )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load daily bars.") from exc

        if not rows:
            return []

        bars: list[DailyBar] = []
        for row in rows:
            trade_date = _parse_iso_date(row.get("date"))
            if trade_date is None:
                continue

            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_as_optional_float(row.get("open")),
                    high=_as_optional_float(row.get("high")),
                    low=_as_optional_float(row.get("low")),
                    close=_as_optional_float(row.get("close")),
                    volume=_as_optional_float(row.get("volume")),
                    amount=_as_optional_float(row.get("amount")),
                    adjustment_mode=adjustment_mode,
                    source=self.name,
                )
            )

        return bars

    def get_stock_universe(self) -> list[UniverseItem]:
        self._ensure_available()

        try:
            with self.session_scope():
                bs = self._get_active_module()
                rows = _result_to_rows(bs.query_all_stock(day=""))
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load stock universe.") from exc

        if not rows:
            return []

        items: list[UniverseItem] = []
        for row in rows:
            raw_code = _as_optional_string(row.get("code"))
            name = _as_optional_string(row.get("code_name"))
            if raw_code is None or name is None:
                continue

            try:
                canonical_symbol = canonical_symbol_from_provider_symbol(raw_code)
                parts = parse_symbol(canonical_symbol)
            except Exception:
                continue

            items.append(
                UniverseItem(
                    symbol=parts.canonical,
                    code=parts.code,
                    exchange=parts.exchange,
                    name=name,
                    status="active",
                    source=self.name,
                )
            )

        return items

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        return []

    def get_stock_financial_summary_raw(self, symbol: str) -> Optional[dict[str, Any]]:
        """Return a provider-specific raw financial payload for centralized mapping."""
        self._ensure_available()
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with self.session_scope():
                bs = self._get_active_module()
                profit_rows = _query_optional_rows(
                    bs.query_profit_data,
                    code=baostock_symbol,
                    year="",
                    quarter="",
                )
                operation_rows = _query_optional_rows(
                    bs.query_operation_data,
                    code=baostock_symbol,
                    year="",
                    quarter="",
                )
                growth_rows = _query_optional_rows(
                    bs.query_growth_data,
                    code=baostock_symbol,
                    year="",
                    quarter="",
                )
                balance_rows = _query_optional_rows(
                    bs.query_balance_data,
                    code=baostock_symbol,
                    year="",
                    quarter="",
                )
                dupont_rows = _query_optional_rows(
                    bs.query_dupont_data,
                    code=baostock_symbol,
                    year="",
                    quarter="",
                )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load financial summary.") from exc

        return _merge_financial_payload_rows(
            symbol=symbol,
            datasets={
                "profit": profit_rows,
                "operation": operation_rows,
                "growth": growth_rows,
                "balance": balance_rows,
                "dupont": dupont_rows,
            },
        )

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """Compatibility shim. Service should prefer the raw payload method."""
        return None

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise ProviderError("BaoStock is not installed or unavailable.")

    def _get_active_module(self) -> Any:
        if self._logged_in_module is None:
            raise ProviderError("BaoStock session is not active.")
        return self._logged_in_module


def _get_baostock_module() -> Any:
    try:
        return importlib.import_module("baostock")
    except Exception as exc:  # pragma: no cover
        raise ProviderError("BaoStock is not installed or unavailable.") from exc


def _login_baostock(baostock_module: Any) -> None:
    login_result = baostock_module.login()
    if getattr(login_result, "error_code", "") != "0":
        raise ProviderError("BaoStock login failed.")


def _result_to_rows(result: Any) -> list[dict[str, Any]]:
    if result is None:
        raise ProviderError("BaoStock returned an empty query result object.")

    if getattr(result, "error_code", "") != "0":
        raise ProviderError("BaoStock query failed.")

    rows = []
    raw_fields = getattr(result, "fields", [])
    if raw_fields is None:
        return rows

    fields = list(raw_fields)
    next_method = getattr(result, "next", None)
    if not callable(next_method):
        raise ProviderError("BaoStock returned an unexpected query result format.")

    while next_method():
        values = result.get_row_data()
        if values is None:
            continue
        rows.append(dict(zip(fields, values)))

    return rows


def _query_optional_rows(query_func: Any, **kwargs: Any) -> list[dict[str, Any]]:
    try:
        return _result_to_rows(query_func(**kwargs))
    except ProviderError:
        return []


def _merge_financial_payload_rows(
    *,
    symbol: str,
    datasets: dict[str, list[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    merged_by_period: dict[str, dict[str, Any]] = {}

    for dataset_name, rows in datasets.items():
        for row in rows:
            report_period = _extract_report_period(row)
            if report_period is None:
                continue
            bucket = merged_by_period.setdefault(
                report_period,
                {
                    "symbol": symbol,
                    "report_period": report_period,
                    "source": "baostock",
                },
            )
            bucket[dataset_name] = row

    if not merged_by_period:
        return None

    latest_period = max(merged_by_period)
    return merged_by_period[latest_period]


def _extract_report_period(row: dict[str, Any]) -> Optional[str]:
    candidates = (
        row.get("statDate"),
        row.get("pubDate"),
        row.get("calendar_date"),
        row.get("reportDate"),
        row.get("endDate"),
    )
    for candidate in candidates:
        text = _as_optional_string(candidate)
        if text and len(text) >= 10 and "-" in text:
            return text[:10]

    year = _as_optional_string(row.get("year"))
    quarter_text = _as_optional_string(row.get("quarter"))
    if year is None or quarter_text is None:
        return None

    normalized_quarter = {
        "1": "03-31",
        "01": "03-31",
        "q1": "03-31",
        "Q1": "03-31",
        "2": "06-30",
        "02": "06-30",
        "q2": "06-30",
        "Q2": "06-30",
        "3": "09-30",
        "03": "09-30",
        "q3": "09-30",
        "Q3": "09-30",
        "4": "12-31",
        "04": "12-31",
        "q4": "12-31",
        "Q4": "12-31",
    }.get(quarter_text)
    if normalized_quarter is None:
        return None
    return "{year}-{quarter}".format(year=year[:4], quarter=normalized_quarter)


def _format_baostock_date(value: Optional[date]) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _format_baostock_adjustflag(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "raw": "3",
        "qfq": "2",
        "hfq": "1",
    }
    mapped = mapping.get(normalized)
    if mapped is None:
        raise ProviderError(
            "Unsupported adjustment mode for BaoStock: {value}".format(value=value)
        )
    return mapped


def _parse_iso_date(value: Any) -> Optional[date]:
    text = _as_optional_string(value)
    if text is None:
        return None

    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _map_trade_status(value: Any) -> Optional[str]:
    text = _as_optional_string(value)
    if text is None:
        return None
    return "active" if text == "1" else "inactive"


def _as_optional_string(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def _as_optional_float(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    try:
        parsed = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in {"", "--", "nan", "None"}:
        return True
    return False
