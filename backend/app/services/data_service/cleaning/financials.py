"""财务摘要清洗入口。"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional, Sequence

from app.schemas.research_inputs import FinancialSummary
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.cleaning.field_maps import map_financial_summary_row
from app.services.data_service.cleaning.quality import (
    aggregate_financial_cleaning_summary,
)
from app.services.data_service.cleaning.rules import validate_financial_summary_row
from app.services.data_service.cleaning.types import (
    is_missing_value,
    parse_financial_amount_to_yuan,
    parse_financial_percent,
    parse_financial_report_period_and_type,
    to_optional_float,
)
from app.services.data_service.contracts.financials import (
    CleanFinancialSummary,
    CleanFinancialSummaryResult,
)
from app.services.data_service.exceptions import InvalidSymbolError
from app.services.data_service.normalize import normalize_symbol

_SELECTION_WEIGHT = {
    "ok": 3,
    "warning": 2,
    "degraded": 1,
    "failed": 0,
}


def clean_financial_summary(
    *,
    symbol: str,
    rows: Sequence[FinancialSummary | Mapping[str, Any]],
    as_of_date: Optional[date] = None,
    default_source: Optional[str] = None,
    provider_used: Optional[str] = None,
    fallback_applied: bool = False,
    fallback_reason: Optional[str] = None,
    source_mode: Optional[str] = None,
    freshness_mode: Optional[str] = None,
) -> CleanFinancialSummaryResult:
    """清洗并标准化财务摘要。"""
    normalized_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
    cleaned_rows: dict[tuple[str, Optional[date], str], CleanFinancialSummary] = {}
    statuses: list[str] = []
    warning_messages: list[str] = []
    missing_fields: list[str] = []
    coerced_fields: list[str] = []
    dropped_rows = 0
    dropped_duplicate_rows = 0

    for index, row in enumerate(rows):
        raw_item = _row_to_mapping(row, default_source=default_source)
        if raw_item is None:
            dropped_rows += 1
            warning_messages.append("row_{index}:unsupported_row_type".format(index=index))
            continue

        mapped = map_financial_summary_row(raw_item, default_source=default_source)
        normalized_symbol = _normalize_financial_symbol(
            raw_symbol=mapped.get("symbol"),
            fallback_symbol=symbol,
        )
        normalized_name = _normalize_name(mapped.get("name")) or normalized_symbol
        source = str(mapped.get("source") or default_source or "unknown").strip().lower()

        report_period, report_type, report_period_coerced = parse_financial_report_period_and_type(
            mapped.get("report_period"),
            mapped.get("report_type"),
        )
        row_coerced_fields: list[str] = []
        row_warnings: list[str] = []
        row_missing_fields: list[str] = []

        if report_period_coerced:
            row_coerced_fields.append("report_period")
        if report_type == "unknown":
            row_warnings.append("unknown_report_type")

        revenue, revenue_coerced = _parse_amount_field(mapped.get("revenue"), "revenue", row_warnings)
        net_profit, net_profit_coerced = _parse_amount_field(
            mapped.get("net_profit"),
            "net_profit",
            row_warnings,
        )
        revenue_yoy, revenue_yoy_coerced = _parse_percent_field(
            mapped.get("revenue_yoy"),
            "revenue_yoy",
            row_warnings,
        )
        net_profit_yoy, net_profit_yoy_coerced = _parse_percent_field(
            mapped.get("net_profit_yoy"),
            "net_profit_yoy",
            row_warnings,
        )
        roe, roe_coerced = _parse_percent_field(mapped.get("roe"), "roe", row_warnings)
        gross_margin, gross_margin_coerced = _parse_percent_field(
            mapped.get("gross_margin"),
            "gross_margin",
            row_warnings,
        )
        debt_ratio, debt_ratio_coerced = _parse_percent_field(
            mapped.get("debt_ratio"),
            "debt_ratio",
            row_warnings,
        )
        eps, eps_coerced = _parse_float_field(mapped.get("eps"), "eps", row_warnings)
        bps, bps_coerced = _parse_float_field(mapped.get("bps"), "bps", row_warnings)

        if revenue_coerced:
            row_coerced_fields.append("revenue")
        if net_profit_coerced:
            row_coerced_fields.append("net_profit")
        if revenue_yoy_coerced:
            row_coerced_fields.append("revenue_yoy")
        if net_profit_yoy_coerced:
            row_coerced_fields.append("net_profit_yoy")
        if roe_coerced:
            row_coerced_fields.append("roe")
        if gross_margin_coerced:
            row_coerced_fields.append("gross_margin")
        if debt_ratio_coerced:
            row_coerced_fields.append("debt_ratio")
        if eps_coerced:
            row_coerced_fields.append("eps")
        if bps_coerced:
            row_coerced_fields.append("bps")

        row_status, rule_warnings, missing_from_rules = validate_financial_summary_row(
            report_period=report_period,
            report_type=report_type,
            revenue=revenue,
            revenue_yoy=revenue_yoy,
            net_profit=net_profit,
            net_profit_yoy=net_profit_yoy,
            roe=roe,
            gross_margin=gross_margin,
            debt_ratio=debt_ratio,
            eps=eps,
            bps=bps,
        )
        row_warnings.extend(rule_warnings)
        row_missing_fields.extend(missing_from_rules)

        statuses.append(row_status)
        warning_messages.extend(
            "row_{index}:{warning}".format(index=index, warning=warning)
            for warning in row_warnings
        )
        missing_fields.extend(row_missing_fields)
        coerced_fields.extend(row_coerced_fields)

        clean_row = CleanFinancialSummary(
            symbol=normalized_symbol,
            name=normalized_name,
            report_period=report_period,
            report_type=report_type,
            revenue=revenue,
            revenue_yoy=revenue_yoy,
            net_profit=net_profit,
            net_profit_yoy=net_profit_yoy,
            roe=roe,
            gross_margin=gross_margin,
            debt_ratio=debt_ratio,
            eps=eps,
            bps=bps,
            source=source,
            as_of_date=normalized_as_of_date,
            quality_status=row_status,  # type: ignore[arg-type]
            cleaning_warnings=list(dict.fromkeys(row_warnings)),
            missing_fields=list(dict.fromkeys(row_missing_fields)),
            coerced_fields=list(dict.fromkeys(row_coerced_fields)),
            provider_used=provider_used or source,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            source_mode=source_mode,
            freshness_mode=freshness_mode,
        )

        dedupe_key = (normalized_symbol, report_period, report_type)
        if dedupe_key in cleaned_rows:
            dropped_duplicate_rows += 1
            existing = cleaned_rows[dedupe_key]
            if _is_same_financial_row(existing, clean_row):
                warning_messages.append("row_{index}:duplicate_financial_row".format(index=index))
                continue
            warning_messages.append("row_{index}:conflicting_financial_row".format(index=index))
            cleaned_rows[dedupe_key] = _pick_better_financial_row(existing, clean_row)
            continue

        cleaned_rows[dedupe_key] = clean_row

    selected_summary = _select_latest_financial_summary(list(cleaned_rows.values()))
    summary = aggregate_financial_cleaning_summary(
        statuses=statuses,
        warning_messages=warning_messages,
        total_rows=len(rows),
        output_rows=1 if selected_summary is not None else 0,
        dropped_rows=dropped_rows,
        dropped_duplicate_rows=dropped_duplicate_rows,
        missing_fields=missing_fields,
        coerced_fields=coerced_fields,
    )
    return CleanFinancialSummaryResult(
        summary=selected_summary,
        cleaning_summary=summary,
    )


def _row_to_mapping(
    row: FinancialSummary | Mapping[str, Any],
    *,
    default_source: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if isinstance(row, FinancialSummary):
        payload = row.model_dump()
        if default_source and not payload.get("source"):
            payload["source"] = default_source
        return payload
    if isinstance(row, Mapping):
        payload = dict(row)
        if default_source and not payload.get("source"):
            payload["source"] = default_source
        return payload
    return None


def _normalize_financial_symbol(raw_symbol: Any, fallback_symbol: str) -> str:
    text = str(raw_symbol or "").strip()
    if text == "":
        return normalize_symbol(fallback_symbol)
    try:
        return normalize_symbol(text)
    except InvalidSymbolError:
        return normalize_symbol(fallback_symbol)


def _normalize_name(raw_name: Any) -> Optional[str]:
    if is_missing_value(raw_name):
        return None
    text = str(raw_name).strip()
    if text == "":
        return None
    return " ".join(text.split())


def _parse_amount_field(
    raw_value: Any,
    field_name: str,
    warning_messages: list[str],
) -> tuple[Optional[float], bool]:
    value, coerced = parse_financial_amount_to_yuan(raw_value)
    if value is None and not is_missing_value(raw_value):
        warning_messages.append("invalid_{field_name}".format(field_name=field_name))
    return value, coerced


def _parse_percent_field(
    raw_value: Any,
    field_name: str,
    warning_messages: list[str],
) -> tuple[Optional[float], bool]:
    value, coerced = parse_financial_percent(raw_value)
    if value is None and not is_missing_value(raw_value):
        warning_messages.append("invalid_{field_name}".format(field_name=field_name))
    return value, coerced


def _parse_float_field(
    raw_value: Any,
    field_name: str,
    warning_messages: list[str],
) -> tuple[Optional[float], bool]:
    value, coerced = to_optional_float(raw_value)
    if value is None and not is_missing_value(raw_value):
        warning_messages.append("invalid_{field_name}".format(field_name=field_name))
    return value, coerced


def _is_same_financial_row(
    left: CleanFinancialSummary,
    right: CleanFinancialSummary,
) -> bool:
    return (
        left.revenue == right.revenue
        and left.revenue_yoy == right.revenue_yoy
        and left.net_profit == right.net_profit
        and left.net_profit_yoy == right.net_profit_yoy
        and left.roe == right.roe
        and left.gross_margin == right.gross_margin
        and left.debt_ratio == right.debt_ratio
        and left.eps == right.eps
        and left.bps == right.bps
    )


def _pick_better_financial_row(
    left: CleanFinancialSummary,
    right: CleanFinancialSummary,
) -> CleanFinancialSummary:
    left_weight = _SELECTION_WEIGHT.get(left.quality_status, 0)
    right_weight = _SELECTION_WEIGHT.get(right.quality_status, 0)
    if right_weight > left_weight:
        return right
    if right_weight < left_weight:
        return left
    left_completeness = _financial_completeness_score(left)
    right_completeness = _financial_completeness_score(right)
    if right_completeness > left_completeness:
        return right
    return left


def _financial_completeness_score(summary: CleanFinancialSummary) -> int:
    values = (
        summary.revenue,
        summary.revenue_yoy,
        summary.net_profit,
        summary.net_profit_yoy,
        summary.roe,
        summary.gross_margin,
        summary.debt_ratio,
        summary.eps,
        summary.bps,
    )
    return sum(value is not None for value in values)


def _select_latest_financial_summary(
    rows: list[CleanFinancialSummary],
) -> Optional[CleanFinancialSummary]:
    if not rows:
        return None
    usable_rows = [row for row in rows if row.quality_status != "failed"]
    candidates = usable_rows if usable_rows else rows
    return sorted(
        candidates,
        key=lambda row: (
            row.report_period or date.min,
            _SELECTION_WEIGHT.get(row.quality_status, 0),
            _financial_completeness_score(row),
        ),
        reverse=True,
    )[0]
