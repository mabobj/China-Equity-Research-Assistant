"""Centralized normalization helpers for symbols, dates, units, and bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
from typing import Any, Iterable, Literal, Mapping

from app.schemas.market_data import DailyBar
from app.services.data_service.exceptions import InvalidSymbolError

ProviderName = Literal["akshare", "baostock", "cninfo", "mootdx", "tdx_api", "tushare"]
Exchange = Literal["SH", "SZ"]
BoardType = Literal["main_board", "chinext", "star_market", "unknown"]

_CANONICAL_PATTERN = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SZ)$")
_PREFIX_PATTERN = re.compile(r"^(?P<exchange>sh|sz)(?P<code>\d{6})$", re.IGNORECASE)
_RAW_CODE_PATTERN = re.compile(r"^\d{6}$")
_BAOSTOCK_PATTERN = re.compile(r"^(?P<exchange>sh|sz)\.(?P<code>\d{6})$", re.IGNORECASE)

_REPORT_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], tuple[int, int] | None], ...] = (
    (re.compile(r"^(?P<year>\d{4})\s*[-/ ]?Q1$", re.IGNORECASE), (3, 31)),
    (re.compile(r"^(?P<year>\d{4})\s*[-/ ]?Q2$", re.IGNORECASE), (6, 30)),
    (re.compile(r"^(?P<year>\d{4})\s*[-/ ]?Q3$", re.IGNORECASE), (9, 30)),
    (re.compile(r"^(?P<year>\d{4})\s*[-/ ]?Q4$", re.IGNORECASE), (12, 31)),
    (re.compile(r"^(?P<year>\d{4})\s*年报$"), (12, 31)),
    (re.compile(r"^(?P<year>\d{4})\s*(?:半年度报告|半年报|中报)$"), (6, 30)),
    (re.compile(r"^(?P<year>\d{4})\s*(?:第一季度报告|一季报)$"), (3, 31)),
    (re.compile(r"^(?P<year>\d{4})\s*(?:第三季度报告|三季报)$"), (9, 30)),
)


@dataclass(frozen=True)
class SymbolParts:
    """Normalized stock symbol parts."""

    code: str
    exchange: Exchange

    @property
    def canonical(self) -> str:
        return f"{self.code}.{self.exchange}"

    @property
    def akshare_symbol(self) -> str:
        return self.code

    @property
    def baostock_symbol(self) -> str:
        return f"{self.exchange.lower()}.{self.code}"

    @property
    def prefixed_symbol(self) -> str:
        return f"{self.exchange.lower()}{self.code}"

    @property
    def cninfo_symbol(self) -> str:
        return self.code

    @property
    def mootdx_symbol(self) -> str:
        return self.code

    @property
    def tdx_api_symbol(self) -> str:
        return self.prefixed_symbol

    @property
    def tushare_symbol(self) -> str:
        return self.canonical


def normalize_symbol(symbol: str) -> str:
    """Normalize any supported symbol format into canonical form."""
    return parse_symbol(symbol).canonical


def parse_symbol(symbol: str) -> SymbolParts:
    """Parse stock symbol into normalized parts."""
    cleaned = symbol.strip()
    if not cleaned:
        raise InvalidSymbolError("Symbol cannot be empty.")

    upper_symbol = cleaned.upper()
    canonical_match = _CANONICAL_PATTERN.fullmatch(upper_symbol)
    if canonical_match is not None:
        return SymbolParts(
            code=canonical_match.group("code"),
            exchange=canonical_match.group("exchange"),
        )

    prefix_match = _PREFIX_PATTERN.fullmatch(cleaned)
    if prefix_match is not None:
        return SymbolParts(
            code=prefix_match.group("code"),
            exchange=prefix_match.group("exchange").upper(),
        )

    baostock_match = _BAOSTOCK_PATTERN.fullmatch(cleaned)
    if baostock_match is not None:
        return SymbolParts(
            code=baostock_match.group("code"),
            exchange=baostock_match.group("exchange").upper(),
        )

    if _RAW_CODE_PATTERN.fullmatch(cleaned) is not None:
        return SymbolParts(code=cleaned, exchange=_infer_exchange(cleaned))

    raise InvalidSymbolError(
        "Invalid symbol '{symbol}'. Expected formats like 600519, 600519.SH, "
        "sh600519, sz000001, or sh.600519.".format(symbol=symbol),
    )


def convert_symbol_for_provider(symbol: str, provider: ProviderName) -> str:
    """Convert canonical symbol into provider-specific format."""
    parts = parse_symbol(symbol)
    if provider == "akshare":
        return parts.akshare_symbol
    if provider == "baostock":
        return parts.baostock_symbol
    if provider == "cninfo":
        return parts.cninfo_symbol
    if provider == "mootdx":
        return parts.mootdx_symbol
    if provider == "tdx_api":
        return parts.tdx_api_symbol
    if provider == "tushare":
        return parts.tushare_symbol
    raise InvalidSymbolError(
        "Unsupported provider symbol conversion: {provider}".format(provider=provider),
    )


def infer_board_from_symbol(symbol: str) -> BoardType:
    """Infer board type from canonical symbol."""
    parts = parse_symbol(symbol)
    if parts.exchange == "SH" and parts.code.startswith("688"):
        return "star_market"
    if parts.exchange == "SZ" and parts.code.startswith(("300", "301")):
        return "chinext"
    if parts.exchange in {"SH", "SZ"}:
        return "main_board"
    return "unknown"


def canonical_symbol_from_provider_symbol(symbol: str) -> str:
    """Convert provider-style symbol back into canonical symbol."""
    return normalize_symbol(symbol)


def normalize_provider_name(provider: str) -> str:
    """Normalize provider aliases into stable internal names."""
    normalized = provider.strip().lower()
    aliases = {
        "akshare_api": "akshare",
        "aksharepro": "akshare",
        "cninfo.com.cn": "cninfo",
        "juchao": "cninfo",
        "tdx-api": "tdx_api",
        "tdxapi": "tdx_api",
    }
    return aliases.get(normalized, normalized)


def parse_provider_date(value: Any) -> date | None:
    """Parse provider date input into a date object."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if text == "":
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    chinese_match = re.match(
        r"^(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日?$",
        text,
    )
    if chinese_match is not None:
        return date(
            int(chinese_match.group("year")),
            int(chinese_match.group("month")),
            int(chinese_match.group("day")),
        )
    return None


def parse_provider_datetime(value: Any) -> datetime | None:
    """Parse provider datetime input into a datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = str(value).strip()
    if text == "":
        return None
    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y%m%d%H%M%S",
    ):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def normalize_price_to_yuan(value: float | None, *, source: str) -> float | None:
    """Normalize quote price into yuan."""
    if value is None:
        return None
    if normalize_provider_name(source) == "tdx_api":
        return value / 1000.0
    return value


def normalize_volume_to_shares(value: float | None, *, source: str) -> float | None:
    """Normalize traded volume into shares."""
    if value is None:
        return None
    normalized_source = normalize_provider_name(source)
    if normalized_source in {"tdx_api", "mootdx", "akshare"}:
        return value * 100.0
    return value


def normalize_amount_to_yuan(value: float | None, *, source: str) -> float | None:
    """Normalize turnover amount into yuan."""
    if value is None:
        return None
    if normalize_provider_name(source) == "tdx_api":
        return value / 1000.0
    return value


def normalize_financial_amount_to_yuan(value: float | None) -> float | None:
    """Normalize financial amount fields into yuan."""
    return value


def normalize_financial_percent(value: float | None) -> float | None:
    """Normalize financial ratio fields into percentage points."""
    if value is None:
        return None
    if value != 0 and -1.0 < value < 1.0:
        return value * 100.0
    return value


def normalize_financial_report_period(value: Any) -> date | None:
    """Normalize financial report period into the unified date form."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if text == "":
        return None

    upper_text = text.upper()
    for pattern, month_day in _REPORT_PERIOD_PATTERNS:
        match = pattern.fullmatch(text) or pattern.fullmatch(upper_text)
        if match is not None and month_day is not None:
            return date(int(match.group("year")), month_day[0], month_day[1])

    return parse_provider_date(text)


def normalize_financial_report_type(
    value: Any,
    *,
    report_period: date | None = None,
) -> str:
    """Normalize financial report type into q1/half/q3/annual/ttm/unknown."""
    if value is not None:
        normalized = str(value).strip().lower()
        mapping = {
            "q1": "q1",
            "quarter1": "q1",
            "first_quarter": "q1",
            "half": "half",
            "h1": "half",
            "semiannual": "half",
            "half_year": "half",
            "q3": "q3",
            "quarter3": "q3",
            "third_quarter": "q3",
            "annual": "annual",
            "year": "annual",
            "yearly": "annual",
            "ttm": "ttm",
            "unknown": "unknown",
            "一季报": "q1",
            "第一季度报告": "q1",
            "半年报": "half",
            "半年度报告": "half",
            "中报": "half",
            "三季报": "q3",
            "第三季度报告": "q3",
            "年报": "annual",
        }
        if normalized in mapping:
            return mapping[normalized]
        if "ttm" in normalized or "滚动" in normalized:
            return "ttm"

    if report_period is None:
        return "unknown"
    month_day = (report_period.month, report_period.day)
    if month_day == (3, 31):
        return "q1"
    if month_day == (6, 30):
        return "half"
    if month_day == (9, 30):
        return "q3"
    if month_day == (12, 31):
        return "annual"
    return "unknown"


def normalize_adjustment_mode(value: Any, *, source: str | None = None) -> str:
    """Normalize adjustment mode into raw/qfq/hfq."""
    if value is None:
        return "raw"
    normalized = str(value).strip().lower()
    mapping = {
        "": "raw",
        "0": "raw",
        "3": "raw",
        "raw": "raw",
        "none": "raw",
        "1": "hfq",
        "hfq": "hfq",
        "2": "qfq",
        "qfq": "qfq",
    }
    return mapping.get(normalized, "raw")


def normalize_trading_status(value: Any) -> str | None:
    """Normalize trading status labels."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"", "none", "unknown"}:
        return None
    if normalized in {"trading", "trade", "normal", "active"}:
        return "normal"
    if normalized in {"halt", "halted", "suspend", "suspended", "停牌"}:
        return "suspended"
    if normalized in {"delist", "delisted", "退市"}:
        return "delisted"
    if normalized in {"st", "*st"}:
        return "special_treatment"
    return normalized


def normalize_corporate_action_flags(value: Any) -> list[str]:
    """Normalize corporate action flags into a stable unique list."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",")]
    elif isinstance(value, Iterable):
        candidates = [str(item).strip() for item in value]
    else:
        candidates = [str(value).strip()]
    normalized: list[str] = []
    for item in candidates:
        if not item:
            continue
        lowered = item.lower()
        if lowered not in normalized:
            normalized.append(lowered)
    return normalized


def normalize_daily_bar_rows(
    rows: Iterable[DailyBar | Mapping[str, Any]],
    *,
    symbol: str,
    default_source: str,
) -> list[DailyBar]:
    """Normalize provider bar rows into unified DailyBar objects."""
    canonical_symbol = normalize_symbol(symbol)
    normalized_bars: list[DailyBar] = []
    for row in rows:
        if isinstance(row, DailyBar):
            source = row.source or default_source
            normalized_bars.append(
                row.model_copy(
                    update={
                        "symbol": canonical_symbol,
                        "open": normalize_price_to_yuan(row.open, source=source),
                        "high": normalize_price_to_yuan(row.high, source=source),
                        "low": normalize_price_to_yuan(row.low, source=source),
                        "close": normalize_price_to_yuan(row.close, source=source),
                        "volume": normalize_volume_to_shares(row.volume, source=source),
                        "amount": normalize_amount_to_yuan(row.amount, source=source),
                        "adjustment_mode": normalize_adjustment_mode(
                            row.adjustment_mode,
                            source=source,
                        ),
                        "trading_status": normalize_trading_status(row.trading_status),
                        "corporate_action_flags": normalize_corporate_action_flags(
                            row.corporate_action_flags,
                        ),
                        "source": normalize_provider_name(source),
                    }
                )
            )
            continue

        row_mapping = dict(row)
        source = normalize_provider_name(str(row_mapping.get("source") or default_source))
        trade_date = parse_provider_date(row_mapping.get("trade_date") or row_mapping.get("date"))
        if trade_date is None:
            continue
        normalized_bars.append(
            DailyBar(
                symbol=canonical_symbol,
                trade_date=trade_date,
                open=normalize_price_to_yuan(_coerce_float(row_mapping.get("open")), source=source),
                high=normalize_price_to_yuan(_coerce_float(row_mapping.get("high")), source=source),
                low=normalize_price_to_yuan(_coerce_float(row_mapping.get("low")), source=source),
                close=normalize_price_to_yuan(_coerce_float(row_mapping.get("close")), source=source),
                volume=normalize_volume_to_shares(_coerce_float(row_mapping.get("volume")), source=source),
                amount=normalize_amount_to_yuan(_coerce_float(row_mapping.get("amount")), source=source),
                adjustment_mode=normalize_adjustment_mode(
                    row_mapping.get("adjustment_mode"),
                    source=source,
                ),
                trading_status=normalize_trading_status(row_mapping.get("trading_status")),
                corporate_action_flags=normalize_corporate_action_flags(
                    row_mapping.get("corporate_action_flags"),
                ),
                source=source,
            )
        )
    return sorted(normalized_bars, key=lambda item: item.trade_date)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return None if math.isnan(parsed) else parsed
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return None if math.isnan(parsed) else parsed


def _infer_exchange(code: str) -> Exchange:
    if code.startswith(("5", "6", "9")) or code.startswith("688"):
        return "SH"
    return "SZ"
