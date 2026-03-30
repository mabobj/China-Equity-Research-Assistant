"""bars 行级业务规则校验。"""

from __future__ import annotations

from typing import Tuple


def validate_bar_row(
    *,
    open_price: float | None,
    high_price: float | None,
    low_price: float | None,
    close_price: float | None,
    volume: float | None,
    amount: float | None,
) -> Tuple[str, list[str]]:
    """返回 (quality_status, warnings)。"""
    warnings: list[str] = []
    quality_status = "ok"

    if close_price is None or close_price <= 0:
        warnings.append("invalid_close_price")
        return "failed", warnings

    if volume is not None and volume < 0:
        warnings.append("negative_volume")
        return "failed", warnings

    if amount is not None and amount < 0:
        warnings.append("negative_amount")
        return "failed", warnings

    if volume == 0:
        warnings.append("zero_volume_bar")
        quality_status = "warning"

    ohlc_values = (open_price, high_price, low_price, close_price)
    missing_ohlc = any(item is None for item in ohlc_values)
    if missing_ohlc:
        warnings.append("missing_ohlc_fields")
        quality_status = "degraded"
        return quality_status, warnings

    assert open_price is not None
    assert high_price is not None
    assert low_price is not None
    assert close_price is not None

    if high_price < max(open_price, close_price, low_price):
        warnings.append("invalid_high_price_relation")
        return "failed", warnings
    if low_price > min(open_price, close_price, high_price):
        warnings.append("invalid_low_price_relation")
        return "failed", warnings

    return quality_status, warnings
