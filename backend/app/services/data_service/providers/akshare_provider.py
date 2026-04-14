"""AKShare provider for A-share market data and fallback financial summary."""

from __future__ import annotations

from datetime import date, datetime
import importlib
import importlib.util
import math
import random
import re
import time
from typing import Any, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import convert_symbol_for_provider, parse_symbol
from app.services.data_service.providers.base import (
    DAILY_BAR_CAPABILITY,
    FINANCIAL_SUMMARY_CAPABILITY,
    PROFILE_CAPABILITY,
    UNIVERSE_CAPABILITY,
)

_COL_STOCK_NAME = "\u80a1\u7968\u7b80\u79f0"
_COL_INDUSTRY = "\u884c\u4e1a"
_COL_LIST_DATE = "\u4e0a\u5e02\u65f6\u95f4"
_COL_TOTAL_MV = "\u603b\u5e02\u503c"
_COL_FLOAT_MV = "\u6d41\u901a\u5e02\u503c"
_COL_TRADE_DATE = "\u65e5\u671f"
_COL_OPEN = "\u5f00\u76d8"
_COL_HIGH = "\u6700\u9ad8"
_COL_LOW = "\u6700\u4f4e"
_COL_CLOSE = "\u6536\u76d8"
_COL_VOLUME = "\u6210\u4ea4\u91cf"
_COL_AMOUNT = "\u6210\u4ea4\u989d"
_COL_REPORT_PERIOD = "\u62a5\u544a\u671f"
_COL_REPORT_DATE = "\u62a5\u544a\u65e5\u671f"


class AkshareProvider:
    """AKShare provider."""

    name = "akshare"
    capabilities = (
        PROFILE_CAPABILITY,
        DAILY_BAR_CAPABILITY,
        UNIVERSE_CAPABILITY,
        FINANCIAL_SUMMARY_CAPABILITY,
    )

    def __init__(
        self,
        daily_bars_max_retries: int = 4,
        daily_bars_retry_backoff_seconds: float = 0.8,
        daily_bars_retry_jitter_seconds: float = 0.2,
    ) -> None:
        self._daily_bars_max_retries = max(1, daily_bars_max_retries)
        self._daily_bars_retry_backoff_seconds = max(0.0, daily_bars_retry_backoff_seconds)
        self._daily_bars_retry_jitter_seconds = max(0.0, daily_bars_retry_jitter_seconds)

    def is_available(self) -> bool:
        return importlib.util.find_spec("akshare") is not None

    def get_unavailable_reason(self) -> Optional[str]:
        if self.is_available():
            return None
        return "AKShare is not installed or unavailable."

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
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
        name = _as_optional_string(items.get(_COL_STOCK_NAME)) or parts.code

        return StockProfile(
            symbol=parts.canonical,
            code=parts.code,
            exchange=parts.exchange,
            name=name,
            industry=_as_optional_string(items.get(_COL_INDUSTRY)),
            list_date=_parse_compact_date(items.get(_COL_LIST_DATE)),
            status="active",
            total_market_cap=_as_optional_float(items.get(_COL_TOTAL_MV)),
            circulating_market_cap=_as_optional_float(items.get(_COL_FLOAT_MV)),
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
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)
        ak_symbol = convert_symbol_for_provider(symbol, "akshare")

        frame = self._load_daily_frame_with_retry(
            ak=ak,
            ak_symbol=ak_symbol,
            start_date=start_date,
            end_date=end_date,
            adjustment_mode=adjustment_mode,
        )

        if frame is None or frame.empty:
            return []

        bars: list[DailyBar] = []
        for _, row in frame.iterrows():
            trade_date = _parse_flexible_date(row.get(_COL_TRADE_DATE))
            if trade_date is None:
                continue

            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_as_optional_float(row.get(_COL_OPEN)),
                    high=_as_optional_float(row.get(_COL_HIGH)),
                    low=_as_optional_float(row.get(_COL_LOW)),
                    close=_as_optional_float(row.get(_COL_CLOSE)),
                    volume=_as_optional_float(row.get(_COL_VOLUME)),
                    amount=_as_optional_float(row.get(_COL_AMOUNT)),
                    adjustment_mode=adjustment_mode,
                    source=self.name,
                )
            )

        return bars

    def _load_daily_frame_with_retry(
        self,
        ak: Any,
        ak_symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
        adjustment_mode: str = "raw",
    ) -> Any:
        last_error: Optional[Exception] = None
        attempts_used = 0

        for attempt in range(1, self._daily_bars_max_retries + 1):
            attempts_used = attempt
            try:
                return ak.stock_zh_a_hist(
                    symbol=ak_symbol,
                    period="daily",
                    start_date=_format_akshare_date(start_date),
                    end_date=_format_akshare_date(end_date),
                    adjust=_format_akshare_adjustment_mode(adjustment_mode),
                )
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                last_error = exc
                if attempt >= self._daily_bars_max_retries:
                    break
                if not _is_transient_akshare_error(exc):
                    break

                backoff_seconds = (
                    self._daily_bars_retry_backoff_seconds * (2 ** (attempt - 1))
                    + random.uniform(0.0, self._daily_bars_retry_jitter_seconds)
                )
                time.sleep(backoff_seconds)

        if last_error is None:
            raise ProviderError("AKShare failed to load daily bars.")
        raise ProviderError(
            "AKShare failed to load daily bars after {attempts} attempts.".format(
                attempts=attempts_used
            )
        ) from last_error

    def get_stock_universe(self) -> list[UniverseItem]:
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
        self._ensure_available()
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)

        try:
            frame = ak.stock_financial_analysis_indicator_em(
                symbol=parts.canonical,
                indicator="\u6309\u62a5\u544a\u671f",
            )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load financial summary.") from exc

        if frame is None or frame.empty:
            return None

        latest_row = _select_latest_financial_row(frame)
        if latest_row is None:
            return None

        return {
            "symbol": parts.canonical,
            "name": (
                _pick_first_string(
                    latest_row,
                    [
                        "SECURITY_NAME_ABBR",
                        "SECURITY_NAME",
                        "SEC_NAME",
                        "NAME",
                        _COL_STOCK_NAME,
                        "\u540d\u79f0",
                    ],
                )
                or _pick_first_string_by_key_fragments(
                    latest_row,
                    ["NAME", "\u7b80\u79f0", "\u80a1\u7968\u540d\u79f0"],
                )
                or parts.code
            ),
            "row": latest_row,
            "source": self.name,
        }

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        raw_payload = self.get_stock_financial_summary_raw(symbol)
        if raw_payload is None:
            return None

        parts = parse_symbol(symbol)
        latest_row = raw_payload["row"]
        return FinancialSummary(
            symbol=parts.canonical,
            name=raw_payload["name"] or parts.code,
            report_period=_parse_flexible_date(
                _pick_first_value(
                    latest_row,
                    ["REPORT_DATE", "REPORT_PERIOD", "NOTICE_DATE", _COL_REPORT_PERIOD, _COL_REPORT_DATE],
                )
            ),
            revenue=_pick_first_float_by_key_fragments(
                latest_row,
                ["TOTALOPERATEINCOME", "OPERATEINCOME", "TOTALREVENUE", "\u8425\u4e1a\u603b\u6536\u5165", "\u8425\u4e1a\u6536\u5165", "\u8425\u6536"],
            ),
            revenue_yoy=_pick_first_float_by_key_fragments(
                latest_row,
                ["YSTZ", "INCOMEYOY", "\u6536\u5165\u540c\u6bd4", "\u8425\u6536\u540c\u6bd4", "\u8425\u4e1a\u603b\u6536\u5165\u540c\u6bd4", "\u8425\u4e1a\u6536\u5165\u540c\u6bd4"],
            ),
            net_profit=_pick_first_float_by_key_fragments(
                latest_row,
                ["PARENTNETPROFIT", "NETPROFIT", "NETINCOME", "\u5f52\u6bcd\u51c0\u5229\u6da6", "\u51c0\u5229\u6da6"],
            ),
            net_profit_yoy=_pick_first_float_by_key_fragments(
                latest_row,
                ["SJLTZ", "PROFITYOY", "\u51c0\u5229\u6da6\u540c\u6bd4", "\u5f52\u6bcd\u51c0\u5229\u6da6\u540c\u6bd4"],
            ),
            roe=_pick_first_float_by_key_fragments(
                latest_row,
                ["ROE", "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387", "\u52a0\u6743\u51c0\u8d44\u4ea7\u6536\u76ca\u7387"],
            ),
            gross_margin=_pick_first_float_by_key_fragments(
                latest_row,
                ["GROSSMARGIN", "\u9500\u552e\u6bdb\u5229\u7387", "\u6bdb\u5229\u7387"],
            ),
            debt_ratio=_pick_first_float_by_key_fragments(
                latest_row,
                ["DEBTRATIO", "\u8d44\u4ea7\u8d1f\u503a\u7387", "\u8d1f\u503a\u7387"],
            ),
            eps=_pick_first_float_by_key_fragments(
                latest_row,
                ["BASICEPS", "EPS", "\u6bcf\u80a1\u6536\u76ca"],
            ),
            bps=_pick_first_float_by_key_fragments(
                latest_row,
                ["BPS", "\u6bcf\u80a1\u51c0\u8d44\u4ea7"],
            ),
            source=self.name,
        )

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise ProviderError("AKShare is not installed or unavailable.")


def _get_akshare_module() -> Any:
    try:
        return importlib.import_module("akshare")
    except Exception as exc:  # pragma: no cover
        raise ProviderError("AKShare is not installed or unavailable.") from exc


def _format_akshare_date(value: Optional[date]) -> str:
    if value is None:
        return ""
    return value.strftime("%Y%m%d")


def _format_akshare_adjustment_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "raw":
        return ""
    if normalized in {"qfq", "hfq"}:
        return normalized
    raise ProviderError(
        "Unsupported adjustment mode for AKShare: {value}".format(value=value)
    )


def _parse_compact_date(value: Any) -> Optional[date]:
    text = _as_optional_string(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_flexible_date(value: Any) -> Optional[date]:
    text = _as_optional_string(value)
    if text is None:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _as_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "--", "nan", "None"}:
        return None
    return text


def _as_optional_float(value: Any) -> Optional[float]:
    text = _as_optional_string(value)
    if text is None:
        return None

    normalized = (
        text.replace(",", "")
        .replace("%", "")
        .replace("\u5143", "")
        .replace("\u80a1", "")
    )
    try:
        parsed = float(normalized)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _pick_first_value(row: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in row and _as_optional_string(row[key]) is not None:
            return row[key]
    return None


def _pick_first_string(row: dict[str, Any], candidates: list[str]) -> Optional[str]:
    value = _pick_first_value(row, candidates)
    return _as_optional_string(value)


def _pick_first_string_by_key_fragments(
    row: dict[str, Any],
    fragments: list[str],
) -> Optional[str]:
    normalized_fragments = [_normalize_key(fragment) for fragment in fragments]
    for key, value in row.items():
        normalized_key = _normalize_key(key)
        if any(fragment in normalized_key for fragment in normalized_fragments):
            text = _as_optional_string(value)
            if text is not None:
                return text
    return None


def _pick_first_float_by_key_fragments(
    row: dict[str, Any],
    fragments: list[str],
) -> Optional[float]:
    normalized_fragments = [_normalize_key(fragment) for fragment in fragments]
    for key, value in row.items():
        normalized_key = _normalize_key(key)
        if any(fragment in normalized_key for fragment in normalized_fragments):
            parsed = _as_optional_float(value)
            if parsed is not None:
                return parsed
    return None


def _normalize_key(value: Any) -> str:
    text = _as_optional_string(value)
    if text is None:
        return ""
    return re.sub(r"[\s_\-:/()（）%]", "", text).upper()


def _select_latest_financial_row(frame: Any) -> Optional[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return None

    rows: list[dict[str, Any]] = [dict(row) for _, row in frame.iterrows()]
    if not rows:
        return None

    def sort_key(row: dict[str, Any]) -> tuple[date, int]:
        report_date = _parse_flexible_date(
            _pick_first_value(
                row,
                ["REPORT_DATE", "REPORT_PERIOD", "NOTICE_DATE", _COL_REPORT_PERIOD, _COL_REPORT_DATE],
            )
        ) or date(1900, 1, 1)
        non_empty_count = sum(
            1 for value in row.values() if _as_optional_string(value) is not None
        )
        return (report_date, non_empty_count)

    rows.sort(key=sort_key, reverse=True)
    return rows[0]


def _is_transient_akshare_error(error: Exception) -> bool:
    message = "{error_type}:{message}".format(
        error_type=type(error).__name__,
        message=str(error),
    ).lower()
    transient_markers = (
        "connection aborted",
        "remote disconnected",
        "read timed out",
        "timed out",
        "temporary failure",
        "connection reset",
    )
    return any(marker in message for marker in transient_markers)
