"""集中管理 symbol、日期与行情单位标准化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
from typing import Any, Iterable, Literal

from app.schemas.market_data import DailyBar
from app.services.data_service.exceptions import InvalidSymbolError

ProviderName = Literal["akshare", "baostock", "cninfo", "mootdx", "tdx_api"]
Exchange = Literal["SH", "SZ"]

_CANONICAL_PATTERN = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SZ)$")
_PREFIX_PATTERN = re.compile(r"^(?P<exchange>sh|sz)(?P<code>\d{6})$", re.IGNORECASE)
_RAW_CODE_PATTERN = re.compile(r"^\d{6}$")
_BAOSTOCK_PATTERN = re.compile(r"^(?P<exchange>sh|sz)\.(?P<code>\d{6})$", re.IGNORECASE)
_TDX_PREFIXED_PATTERN = re.compile(r"^(?P<exchange>sh|sz)(?P<code>\d{6})$", re.IGNORECASE)


@dataclass(frozen=True)
class SymbolParts:
    """标准化后的代码拆分结果。"""

    code: str
    exchange: Exchange

    @property
    def canonical(self) -> str:
        return "{code}.{exchange}".format(code=self.code, exchange=self.exchange)

    @property
    def akshare_symbol(self) -> str:
        return self.code

    @property
    def baostock_symbol(self) -> str:
        return "{exchange}.{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )

    @property
    def prefixed_symbol(self) -> str:
        return "{exchange}{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )

    @property
    def cninfo_symbol(self) -> str:
        return self.code

    @property
    def mootdx_symbol(self) -> str:
        return self.code

    @property
    def tdx_api_symbol(self) -> str:
        return self.prefixed_symbol


def normalize_symbol(symbol: str) -> str:
    """把用户输入统一成 canonical symbol。"""
    return parse_symbol(symbol).canonical


def parse_symbol(symbol: str) -> SymbolParts:
    """解析股票代码并统一为系统内部格式。"""
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
        "Invalid symbol '{symbol}'. Expected formats like 600519, "
        "600519.SH, sh600519, sz000001, or sh.600519.".format(symbol=symbol),
    )


def convert_symbol_for_provider(symbol: str, provider: ProviderName) -> str:
    """把 canonical symbol 转换为 provider 所需格式。"""
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
    raise InvalidSymbolError(
        "Unsupported provider symbol conversion: {provider}".format(provider=provider),
    )


def canonical_symbol_from_provider_symbol(symbol: str) -> str:
    """把 provider 风格代码转换回 canonical symbol。"""
    return normalize_symbol(symbol)


def normalize_provider_name(provider: str) -> str:
    """统一 provider 名称别名。"""
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
    """把 provider 日期值统一解析为 date。"""
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
    chinese_match = re.match(r"^(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日$", text)
    if chinese_match is not None:
        return date(
            int(chinese_match.group("year")),
            int(chinese_match.group("month")),
            int(chinese_match.group("day")),
        )
    return None


def parse_provider_datetime(value: Any) -> datetime | None:
    """把 provider 日期时间值统一解析为 datetime。"""
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
    """把价格统一为元。"""
    if value is None:
        return None
    if normalize_provider_name(source) == "tdx_api":
        return value / 1000.0
    return value


def normalize_volume_to_shares(value: float | None, *, source: str) -> float | None:
    """把成交量统一为股。"""
    if value is None:
        return None
    normalized_source = normalize_provider_name(source)
    if normalized_source in {"tdx_api", "mootdx", "akshare"}:
        return value * 100.0
    return value


def normalize_amount_to_yuan(value: float | None, *, source: str) -> float | None:
    """把成交额统一为元。"""
    if value is None:
        return None
    if normalize_provider_name(source) == "tdx_api":
        return value / 1000.0
    return value


def normalize_daily_bar_rows(
    rows: Iterable[DailyBar],
    *,
    symbol: str | None = None,
    default_source: str | None = None,
) -> list[DailyBar]:
    """把 provider 返回的日线统一为内部单位与 canonical symbol。"""
    normalized_rows: list[DailyBar] = []
    fallback_symbol = normalize_symbol(symbol) if symbol else None
    for row in rows:
        row_source = normalize_provider_name(row.source or default_source or "unknown")
        canonical_symbol = fallback_symbol or normalize_symbol(row.symbol)
        normalized_rows.append(
            DailyBar(
                symbol=canonical_symbol,
                trade_date=parse_provider_date(row.trade_date) or row.trade_date,
                open=normalize_price_to_yuan(_to_optional_float(row.open), source=row_source),
                high=normalize_price_to_yuan(_to_optional_float(row.high), source=row_source),
                low=normalize_price_to_yuan(_to_optional_float(row.low), source=row_source),
                close=normalize_price_to_yuan(_to_optional_float(row.close), source=row_source),
                volume=normalize_volume_to_shares(
                    _to_optional_float(row.volume),
                    source=row_source,
                ),
                amount=normalize_amount_to_yuan(_to_optional_float(row.amount), source=row_source),
                source=row_source,
            )
        )
    return normalized_rows


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _infer_exchange(code: str) -> Exchange:
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    raise InvalidSymbolError(
        "Unable to infer exchange for symbol '{code}'. Please include .SH or .SZ.".format(
            code=code,
        ),
    )
