"""集中管理股票代码标准化与 provider 格式转换。"""

from dataclasses import dataclass
import re
from typing import Literal

from app.services.data_service.exceptions import InvalidSymbolError

ProviderName = Literal["akshare", "baostock", "cninfo"]
Exchange = Literal["SH", "SZ"]

_CANONICAL_PATTERN = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SZ)$")
_PREFIX_PATTERN = re.compile(r"^(?P<exchange>sh|sz)(?P<code>\d{6})$", re.IGNORECASE)
_RAW_CODE_PATTERN = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class SymbolParts:
    """标准化后的代码拆分结果。"""

    code: str
    exchange: Exchange

    @property
    def canonical(self) -> str:
        """返回系统内部统一使用的 canonical symbol。"""
        return "{code}.{exchange}".format(code=self.code, exchange=self.exchange)

    @property
    def akshare_symbol(self) -> str:
        """返回 AKShare 使用的股票代码格式。"""
        return self.code

    @property
    def baostock_symbol(self) -> str:
        """返回 BaoStock 使用的股票代码格式。"""
        return "{exchange}.{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )

    @property
    def prefixed_symbol(self) -> str:
        """返回小写交易所前缀格式。"""
        return "{exchange}{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )

    @property
    def cninfo_symbol(self) -> str:
        """返回 CNINFO 使用的股票代码格式。"""
        return self.code


def normalize_symbol(symbol: str) -> str:
    """将用户输入的代码标准化为 canonical symbol。"""
    return parse_symbol(symbol).canonical


def parse_symbol(symbol: str) -> SymbolParts:
    """解析用户输入的股票代码。"""
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

    if _RAW_CODE_PATTERN.fullmatch(cleaned) is not None:
        return SymbolParts(code=cleaned, exchange=_infer_exchange(cleaned))

    raise InvalidSymbolError(
        "Invalid symbol '{symbol}'. Expected formats like 600519, "
        "600519.SH, sh600519, 000001.SZ, or sz000001.".format(symbol=symbol),
    )


def convert_symbol_for_provider(symbol: str, provider: ProviderName) -> str:
    """将 canonical symbol 转换为 provider 需要的格式。"""
    parts = parse_symbol(symbol)
    if provider == "akshare":
        return parts.akshare_symbol
    if provider == "baostock":
        return parts.baostock_symbol
    if provider == "cninfo":
        return parts.cninfo_symbol
    raise InvalidSymbolError(
        "Unsupported provider symbol conversion: {provider}".format(provider=provider),
    )


def canonical_symbol_from_provider_symbol(symbol: str) -> str:
    """将 provider 风格代码转换回 canonical symbol。"""
    cleaned = symbol.strip().lower()

    if re.fullmatch(r"^(sh|sz)\.\d{6}$", cleaned) is None:
        return normalize_symbol(symbol)

    exchange, code = cleaned.split(".")
    return SymbolParts(code=code, exchange=exchange.upper()).canonical


def _infer_exchange(code: str) -> Exchange:
    """根据六位 A 股代码推断交易所。"""
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    raise InvalidSymbolError(
        "Unable to infer exchange for symbol '{code}'. Please include .SH or .SZ.".format(
            code=code,
        ),
    )
