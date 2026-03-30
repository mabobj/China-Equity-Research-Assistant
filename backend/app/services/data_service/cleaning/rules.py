"""数据清洗业务规则校验。"""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple


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


def validate_financial_summary_row(
    *,
    report_period: Optional[date],
    report_type: str,
    revenue: Optional[float],
    revenue_yoy: Optional[float],
    net_profit: Optional[float],
    net_profit_yoy: Optional[float],
    roe: Optional[float],
    gross_margin: Optional[float],
    debt_ratio: Optional[float],
    eps: Optional[float],
    bps: Optional[float],
) -> tuple[str, list[str], list[str]]:
    """校验财务摘要，返回 (quality_status, warnings, missing_fields)。"""
    warnings: list[str] = []
    missing_fields: list[str] = []

    if report_period is None and report_type not in {"ttm", "unknown"}:
        warnings.append("missing_report_period")

    if report_type == "unknown":
        warnings.append("unknown_report_type")

    core_fields = {
        "revenue": revenue,
        "net_profit": net_profit,
        "roe": roe,
        "debt_ratio": debt_ratio,
    }
    for field_name, field_value in core_fields.items():
        if field_value is None:
            missing_fields.append(field_name)

    if all(value is None for value in core_fields.values()):
        warnings.append("core_financial_fields_all_missing")
        return "failed", warnings, missing_fields

    _append_outlier_warning(
        warnings=warnings,
        field_name="revenue_yoy",
        value=revenue_yoy,
        threshold=1000.0,
    )
    _append_outlier_warning(
        warnings=warnings,
        field_name="net_profit_yoy",
        value=net_profit_yoy,
        threshold=2000.0,
    )
    _append_range_warning(
        warnings=warnings,
        field_name="roe",
        value=roe,
        min_value=-100.0,
        max_value=100.0,
    )
    _append_range_warning(
        warnings=warnings,
        field_name="gross_margin",
        value=gross_margin,
        min_value=-100.0,
        max_value=100.0,
    )
    _append_range_warning(
        warnings=warnings,
        field_name="debt_ratio",
        value=debt_ratio,
        min_value=0.0,
        max_value=100.0,
    )

    if revenue is not None and revenue < 0:
        warnings.append("negative_revenue")
    if net_profit is not None and net_profit < 0:
        warnings.append("negative_net_profit")
    if eps is not None and abs(eps) > 1000:
        warnings.append("eps_outlier")
    if bps is not None and abs(bps) > 100000:
        warnings.append("bps_outlier")

    if "core_financial_fields_all_missing" in warnings:
        return "failed", warnings, missing_fields

    if len(missing_fields) >= 3 or "unknown_report_type" in warnings:
        return "degraded", warnings, missing_fields

    if warnings:
        return "warning", warnings, missing_fields
    return "ok", warnings, missing_fields


def _append_outlier_warning(
    *,
    warnings: list[str],
    field_name: str,
    value: Optional[float],
    threshold: float,
) -> None:
    if value is None:
        return
    if abs(value) > threshold:
        warnings.append("{field}_outlier".format(field=field_name))


def _append_range_warning(
    *,
    warnings: list[str],
    field_name: str,
    value: Optional[float],
    min_value: float,
    max_value: float,
) -> None:
    if value is None:
        return
    if value < min_value or value > max_value:
        warnings.append("{field}_out_of_range".format(field=field_name))
