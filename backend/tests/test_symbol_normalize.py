"""Tests for stock symbol normalization."""

import pytest

from app.services.data_service.exceptions import InvalidSymbolError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    normalize_adjustment_mode,
    normalize_corporate_action_flags,
    normalize_amount_to_yuan,
    normalize_price_to_yuan,
    normalize_trading_status,
    normalize_volume_to_shares,
    normalize_symbol,
    parse_provider_date,
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
    assert convert_symbol_for_provider("600519.SH", "cninfo") == "600519"
    assert convert_symbol_for_provider("600519.SH", "mootdx") == "600519"
    assert convert_symbol_for_provider("600519.SH", "tdx_api") == "sh600519"
    assert canonical_symbol_from_provider_symbol("sz.000001") == "000001.SZ"
    assert canonical_symbol_from_provider_symbol("sh600519") == "600519.SH"


def test_provider_date_and_unit_normalization_are_centralized() -> None:
    """日期与单位标准化应集中在 normalize 层处理。"""
    assert parse_provider_date("20260409").isoformat() == "2026-04-09"
    assert parse_provider_date("2026/04/09").isoformat() == "2026-04-09"
    assert normalize_price_to_yuan(12345.0, source="tdx_api") == 12.345
    assert normalize_volume_to_shares(123.0, source="tdx_api") == 12300.0
    assert normalize_volume_to_shares(123.0, source="akshare") == 12300.0
    assert normalize_volume_to_shares(123.0, source="mootdx") == 12300.0
    assert normalize_amount_to_yuan(12345.0, source="tdx_api") == 12.345


def test_adjustment_and_corporate_action_normalization_are_centralized() -> None:
    assert normalize_adjustment_mode("3", source="baostock") == "raw"
    assert normalize_adjustment_mode("1", source="baostock") == "qfq"
    assert normalize_adjustment_mode("2", source="baostock") == "hfq"
    assert normalize_adjustment_mode("", source="akshare") == "raw"
    assert normalize_trading_status("trading") == "normal"
    assert normalize_trading_status("halt") == "suspended"
    assert normalize_corporate_action_flags("dividend, split , dividend") == [
        "dividend",
        "split",
    ]


@pytest.mark.parametrize("raw_symbol", ["", "abc", "600519.XY", "12345"])
def test_normalize_symbol_rejects_invalid_values(raw_symbol: str) -> None:
    """Invalid symbols should raise a clear validation error."""
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(raw_symbol)
