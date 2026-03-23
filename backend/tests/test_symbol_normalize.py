"""Tests for stock symbol normalization."""

import pytest

from app.services.data_service.exceptions import InvalidSymbolError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    normalize_symbol,
)


@pytest.mark.parametrize(
    ("raw_symbol", "expected_symbol"),
    [
        ("600519", "600519.SH"),
        ("600519.SH", "600519.SH"),
        ("sh600519", "600519.SH"),
        ("000001", "000001.SZ"),
        ("000001.SZ", "000001.SZ"),
        ("sz000001", "000001.SZ"),
        ("300750", "300750.SZ"),
    ],
)
def test_normalize_symbol_returns_canonical_symbol(
    raw_symbol: str,
    expected_symbol: str,
) -> None:
    """Supported input formats should normalize to canonical symbols."""
    assert normalize_symbol(raw_symbol) == expected_symbol


def test_convert_symbol_for_provider_is_centralized() -> None:
    """Provider-specific symbol formats should be generated centrally."""
    assert convert_symbol_for_provider("600519.SH", "akshare") == "600519"
    assert convert_symbol_for_provider("600519.SH", "baostock") == "sh.600519"
    assert canonical_symbol_from_provider_symbol("sz.000001") == "000001.SZ"


@pytest.mark.parametrize("raw_symbol", ["", "abc", "600519.XY", "12345"])
def test_normalize_symbol_rejects_invalid_values(raw_symbol: str) -> None:
    """Invalid symbols should raise a clear validation error."""
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(raw_symbol)
