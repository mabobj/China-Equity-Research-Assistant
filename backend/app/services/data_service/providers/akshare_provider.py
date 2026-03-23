"""AKShare provider wrapper for basic A-share market data."""

from datetime import date, datetime
import importlib
import importlib.util
import math
from typing import Any, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import convert_symbol_for_provider, parse_symbol


class AkshareProvider:
    """Provider wrapper built on top of AKShare."""

    name = "akshare"

    def is_available(self) -> bool:
        """Return whether AKShare is importable."""
        return importlib.util.find_spec("akshare") is not None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """Return one stock profile from AKShare."""
        self._ensure_available()
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)
        ak_symbol = convert_symbol_for_provider(symbol, "akshare")

        try:
            frame = ak.stock_individual_info_em(symbol=ak_symbol)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load stock profile.") from exc

        if frame is None or frame.empty:
            return None

        if "item" not in frame.columns or "value" not in frame.columns:
            raise ProviderError("AKShare returned an unexpected stock profile format.")

        items = {str(row["item"]): row["value"] for _, row in frame.iterrows()}
        name = _as_optional_string(items.get("股票简称")) or parts.code

        return StockProfile(
            symbol=parts.canonical,
            code=parts.code,
            exchange=parts.exchange,
            name=name,
            industry=_as_optional_string(items.get("行业")),
            list_date=_parse_compact_date(items.get("上市时间")),
            status="active",
            total_market_cap=_as_optional_float(items.get("总市值")),
            circulating_market_cap=_as_optional_float(items.get("流通市值")),
            source=self.name,
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """Return daily bars from AKShare."""
        self._ensure_available()
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)
        ak_symbol = convert_symbol_for_provider(symbol, "akshare")

        try:
            frame = ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=_format_akshare_date(start_date),
                end_date=_format_akshare_date(end_date),
                adjust="",
            )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load daily bars.") from exc

        if frame is None or frame.empty:
            return []

        bars: list[DailyBar] = []
        for _, row in frame.iterrows():
            trade_date = _parse_flexible_date(row.get("日期"))
            if trade_date is None:
                continue

            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_as_optional_float(row.get("开盘")),
                    high=_as_optional_float(row.get("最高")),
                    low=_as_optional_float(row.get("最低")),
                    close=_as_optional_float(row.get("收盘")),
                    volume=_as_optional_float(row.get("成交量")),
                    amount=_as_optional_float(row.get("成交额")),
                    source=self.name,
                ),
            )

        return bars

    def get_stock_universe(self) -> list[UniverseItem]:
        """Return the basic A-share universe from AKShare."""
        self._ensure_available()
        ak = _get_akshare_module()

        try:
            frame = ak.stock_info_a_code_name()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load stock universe.") from exc

        if frame is None or frame.empty:
            return []

        items: list[UniverseItem] = []
        for _, row in frame.iterrows():
            code = _as_optional_string(row.get("code"))
            name = _as_optional_string(row.get("name"))
            if code is None or name is None:
                continue

            try:
                parts = parse_symbol(code)
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
        """Raise a provider error if AKShare is unavailable."""
        if not self.is_available():
            raise ProviderError("AKShare is not installed or unavailable.")


def _get_akshare_module() -> Any:
    """Import and return the AKShare module on demand."""
    try:
        return importlib.import_module("akshare")
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ProviderError("AKShare is not installed or unavailable.") from exc


def _format_akshare_date(value: Optional[date]) -> str:
    """Format a date for AKShare query parameters."""
    if value is None:
        return ""
    return value.strftime("%Y%m%d")


def _parse_compact_date(value: Any) -> Optional[date]:
    """Parse compact dates like 20010531."""
    text = _as_optional_string(value)
    if text is None:
        return None

    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_flexible_date(value: Any) -> Optional[date]:
    """Parse provider date fields into ``date`` objects."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = _as_optional_string(value)
    if text is None:
        return None

    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    return None


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
    if _is_missing(value):
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
