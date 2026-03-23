"""Centralized stock symbol normalization and provider conversion."""

from dataclasses import dataclass
import re
from typing import Literal

from app.services.data_service.exceptions import InvalidSymbolError

ProviderName = Literal["akshare", "baostock"]
Exchange = Literal["SH", "SZ"]

_CANONICAL_PATTERN = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SZ)$")
_PREFIX_PATTERN = re.compile(r"^(?P<exchange>sh|sz)(?P<code>\d{6})$", re.IGNORECASE)
_RAW_CODE_PATTERN = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class SymbolParts:
    """Normalized symbol parts and provider-specific variants."""

    code: str
    exchange: Exchange

    @property
    def canonical(self) -> str:
        """Return the canonical internal symbol format."""
        return "{code}.{exchange}".format(code=self.code, exchange=self.exchange)

    @property
    def akshare_symbol(self) -> str:
        """Return the AKShare stock code format."""
        return self.code

    @property
    def baostock_symbol(self) -> str:
        """Return the BaoStock stock code format."""
        return "{exchange}.{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )

    @property
    def prefixed_symbol(self) -> str:
        """Return the lower-case prefixed symbol format."""
        return "{exchange}{code}".format(
            exchange=self.exchange.lower(),
            code=self.code,
        )


def normalize_symbol(symbol: str) -> str:
    """Normalize a user-provided stock symbol to canonical format."""
    return parse_symbol(symbol).canonical


def parse_symbol(symbol: str) -> SymbolParts:
    """Parse a user-provided stock symbol into normalized parts."""
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
    """Convert a symbol to a provider-specific format."""
    parts = parse_symbol(symbol)
    if provider == "akshare":
        return parts.akshare_symbol
    if provider == "baostock":
        return parts.baostock_symbol
    raise InvalidSymbolError(
        "Unsupported provider symbol conversion: {provider}".format(provider=provider),
    )


def canonical_symbol_from_provider_symbol(symbol: str) -> str:
    """Convert provider-style symbols like sh.600519 to canonical format."""
    cleaned = symbol.strip().lower()

    if re.fullmatch(r"^(sh|sz)\.\d{6}$", cleaned) is None:
        return normalize_symbol(symbol)

    exchange, code = cleaned.split(".")
    return SymbolParts(code=code, exchange=exchange.upper()).canonical


def _infer_exchange(code: str) -> Exchange:
    """Infer exchange from a six-digit A-share stock code."""
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    raise InvalidSymbolError(
        "Unable to infer exchange for symbol '{code}'. Please include .SH or .SZ.".format(
            code=code,
        ),
    )
