"""BaoStock provider wrapper for basic A-share market data."""

from datetime import date, datetime
import importlib
import importlib.util
import math
from typing import Any, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    parse_symbol,
)


class BaostockProvider:
    """Provider wrapper built on top of BaoStock."""

    name = "baostock"

    def is_available(self) -> bool:
        """Return whether BaoStock is importable."""
        return importlib.util.find_spec("baostock") is not None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """Return one stock profile from BaoStock."""
        self._ensure_available()
        bs = _get_baostock_module()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with _BaoStockSession(bs):
                result = bs.query_stock_basic(code=baostock_symbol)
                rows = _result_to_rows(result)
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
    ) -> list[DailyBar]:
        """Return daily bars from BaoStock."""
        self._ensure_available()
        bs = _get_baostock_module()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with _BaoStockSession(bs):
                result = bs.query_history_k_data_plus(
                    code=baostock_symbol,
                    fields="date,open,high,low,close,volume,amount",
                    start_date=_format_baostock_date(start_date),
                    end_date=_format_baostock_date(end_date),
                    frequency="d",
                    adjustflag="3",
                )
                rows = _result_to_rows(result)
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
                    source=self.name,
                ),
            )

        return bars

    def get_stock_universe(self) -> list[UniverseItem]:
        """Return the basic A-share universe from BaoStock."""
        self._ensure_available()
        bs = _get_baostock_module()

        try:
            with _BaoStockSession(bs):
                result = bs.query_all_stock(day="")
                rows = _result_to_rows(result)
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
                ),
            )

        return items

    def _ensure_available(self) -> None:
        """Raise a provider error if BaoStock is unavailable."""
        if not self.is_available():
            raise ProviderError("BaoStock is not installed or unavailable.")


class _BaoStockSession:
    """Context manager for BaoStock login and logout."""

    def __init__(self, baostock_module: Any) -> None:
        self._baostock_module = baostock_module

    def __enter__(self) -> "_BaoStockSession":
        login_result = self._baostock_module.login()
        if getattr(login_result, "error_code", "") != "0":
            raise ProviderError("BaoStock login failed.")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._baostock_module.logout()


def _get_baostock_module() -> Any:
    """Import and return the BaoStock module on demand."""
    try:
        return importlib.import_module("baostock")
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ProviderError("BaoStock is not installed or unavailable.") from exc


def _result_to_rows(result: Any) -> list[dict[str, Any]]:
    """Convert a BaoStock result set into a list of row dictionaries."""
    if getattr(result, "error_code", "") != "0":
        raise ProviderError("BaoStock query failed.")

    rows = []
    fields = list(getattr(result, "fields", []))
    while result.next():
        values = result.get_row_data()
        rows.append(dict(zip(fields, values)))

    return rows


def _format_baostock_date(value: Optional[date]) -> str:
    """Format a date for BaoStock query parameters."""
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _parse_iso_date(value: Any) -> Optional[date]:
    """Parse an ISO date string."""
    text = _as_optional_string(value)
    if text is None:
        return None

    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _map_trade_status(value: Any) -> Optional[str]:
    """Map BaoStock status codes into readable status labels."""
    text = _as_optional_string(value)
    if text is None:
        return None
    return "active" if text == "1" else "inactive"


def _as_optional_string(value: Any) -> Optional[str]:
    """Convert a provider value into a clean optional string."""
    if _is_missing(value):
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def _as_optional_float(value: Any) -> Optional[float]:
    """Convert a provider value into an optional float."""
    if _is_missing(value) or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value: Any) -> bool:
    """Return whether a provider value should be treated as missing."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False
