"""Centralized financial summary quality evaluation."""

from __future__ import annotations

from typing import Any, Mapping


def evaluate_financial_summary_quality(
    summary: Mapping[str, Any],
) -> tuple[str, list[str], list[str]]:
    """Return quality_status, missing_fields, warning_messages."""

    report_period = summary.get("report_period")
    report_type = summary.get("report_type")
    revenue = _coerce_float(summary.get("revenue"))
    net_profit = _coerce_float(summary.get("net_profit"))
    roe = _coerce_float(summary.get("roe"))
    debt_ratio = _coerce_float(summary.get("debt_ratio"))
    revenue_yoy = _coerce_float(summary.get("revenue_yoy"))
    net_profit_yoy = _coerce_float(summary.get("net_profit_yoy"))
    gross_margin = _coerce_float(summary.get("gross_margin"))

    missing_fields: list[str] = []
    warnings: list[str] = []

    if report_period is None:
        missing_fields.append("report_period")
    if revenue is None:
        missing_fields.append("revenue")
    if net_profit is None:
        missing_fields.append("net_profit")
    if roe is None:
        missing_fields.append("roe")
    if debt_ratio is None:
        missing_fields.append("debt_ratio")

    if report_type in {None, "", "unknown"}:
        warnings.append("unknown_report_type")

    _append_range_warning(warnings, "roe", roe, -100.0, 100.0)
    _append_range_warning(warnings, "gross_margin", gross_margin, -100.0, 100.0)
    _append_range_warning(warnings, "debt_ratio", debt_ratio, 0.0, 100.0)
    _append_outlier_warning(warnings, "revenue_yoy", revenue_yoy, 1000.0)
    _append_outlier_warning(warnings, "net_profit_yoy", net_profit_yoy, 2000.0)

    primary_fields = ("revenue", "net_profit", "roe")
    secondary_fields = ("gross_margin", "debt_ratio", "eps", "bps")
    primary_missing_count = sum(
        1
        for field_name in primary_fields
        if _coerce_float(summary.get(field_name)) is None
    )
    total_missing_count = len(missing_fields)
    secondary_available_count = sum(
        1
        for field_name in secondary_fields
        if _coerce_float(summary.get(field_name)) is not None
    )
    has_any_value = any(
        _coerce_float(summary.get(field_name)) is not None
        for field_name in (
            "revenue",
            "revenue_yoy",
            "net_profit",
            "net_profit_yoy",
            "roe",
            "gross_margin",
            "debt_ratio",
            "eps",
            "bps",
        )
    )
    all_missing = not has_any_value and report_period is None and report_type in {None, "", "unknown"}

    if all_missing:
        warnings.append("core_financial_fields_all_missing")
        return "failed", _dedupe(missing_fields), _dedupe(warnings)

    if (
        primary_missing_count >= 3
        and secondary_available_count >= 3
        and report_period is not None
    ):
        warnings.append("core_financial_fields_missing_use_secondary_metrics")
        return "warning", _dedupe(missing_fields), _dedupe(warnings)

    if (
        primary_missing_count >= 2
        or total_missing_count >= 6
        or report_type in {None, "", "unknown"}
    ):
        return "degraded", _dedupe(missing_fields), _dedupe(warnings)

    if missing_fields or warnings:
        return "warning", _dedupe(missing_fields), _dedupe(warnings)

    return "ok", [], []


def compare_financial_summary_consistency(
    primary: Mapping[str, Any],
    fallback: Mapping[str, Any],
) -> list[str]:
    """Return warning messages when primary and fallback differ materially."""

    warnings: list[str] = []
    for field_name in ("revenue", "net_profit", "roe", "gross_margin", "debt_ratio"):
        primary_value = _coerce_float(primary.get(field_name))
        fallback_value = _coerce_float(fallback.get(field_name))
        if primary_value is None or fallback_value is None:
            continue
        baseline = max(abs(primary_value), 1.0)
        if abs(primary_value - fallback_value) / baseline > 0.25:
            warnings.append(f"{field_name}_provider_mismatch")
    return _dedupe(warnings)


def _append_range_warning(
    warnings: list[str],
    field_name: str,
    value: float | None,
    min_value: float,
    max_value: float,
) -> None:
    if value is None:
        return
    if value < min_value or value > max_value:
        warnings.append(f"{field_name}_out_of_range")


def _append_outlier_warning(
    warnings: list[str],
    field_name: str,
    value: float | None,
    threshold: float,
) -> None:
    if value is None:
        return
    if abs(value) > threshold:
        warnings.append(f"{field_name}_outlier")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
