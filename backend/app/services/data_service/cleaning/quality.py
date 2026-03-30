"""清洗质量聚合。"""

from __future__ import annotations

from collections import Counter

from app.services.data_service.contracts.announcements import AnnouncementCleaningSummary
from app.services.data_service.contracts.bars import DailyBarsCleaningSummary
from app.services.data_service.contracts.financials import FinancialSummaryCleaningSummary

_STATUS_WEIGHT = {
    "ok": 0,
    "warning": 1,
    "degraded": 2,
    "failed": 3,
}


def aggregate_cleaning_summary(
    *,
    statuses: list[str],
    warning_messages: list[str],
    total_rows: int,
    output_rows: int,
    dropped_rows: int,
    dropped_duplicate_rows: int,
) -> DailyBarsCleaningSummary:
    """构建批量 bars 清洗摘要。"""
    quality_status = "ok"
    if statuses:
        quality_status = max(statuses, key=lambda item: _STATUS_WEIGHT.get(item, 3))
    elif total_rows > 0 and output_rows == 0:
        quality_status = "failed"

    deduped_warnings = _dedupe_preserve_order(warning_messages)
    if quality_status == "ok" and deduped_warnings:
        quality_status = "warning"

    return DailyBarsCleaningSummary(
        quality_status=quality_status,  # type: ignore[arg-type]
        total_rows=total_rows,
        output_rows=output_rows,
        dropped_rows=max(dropped_rows, 0),
        dropped_duplicate_rows=max(dropped_duplicate_rows, 0),
        warning_messages=deduped_warnings,
    )


def aggregate_financial_cleaning_summary(
    *,
    statuses: list[str],
    warning_messages: list[str],
    total_rows: int,
    output_rows: int,
    dropped_rows: int,
    dropped_duplicate_rows: int,
    missing_fields: list[str],
    coerced_fields: list[str],
) -> FinancialSummaryCleaningSummary:
    """构建财务摘要清洗摘要。"""
    quality_status = "ok"
    if statuses:
        quality_status = max(statuses, key=lambda item: _STATUS_WEIGHT.get(item, 3))
    elif total_rows > 0 and output_rows == 0:
        quality_status = "failed"

    deduped_warnings = _dedupe_preserve_order(warning_messages)
    deduped_missing_fields = _dedupe_preserve_order(missing_fields)
    deduped_coerced_fields = _dedupe_preserve_order(coerced_fields)

    if quality_status == "ok" and (deduped_warnings or deduped_missing_fields):
        quality_status = "warning"

    return FinancialSummaryCleaningSummary(
        quality_status=quality_status,  # type: ignore[arg-type]
        total_rows=total_rows,
        output_rows=output_rows,
        dropped_rows=max(dropped_rows, 0),
        dropped_duplicate_rows=max(dropped_duplicate_rows, 0),
        warning_messages=deduped_warnings,
        missing_fields=deduped_missing_fields,
        coerced_fields=deduped_coerced_fields,
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    ordered: list[str] = []
    for value in values:
        if value == "":
            continue
        counts[value] += 1
        if counts[value] == 1:
            ordered.append(value)
    return ordered


def aggregate_announcement_cleaning_summary(
    *,
    statuses: list[str],
    warning_messages: list[str],
    total_rows: int,
    output_rows: int,
    dropped_rows: int,
    dropped_duplicate_rows: int,
) -> AnnouncementCleaningSummary:
    """构建公告清洗摘要。"""
    quality_status = "ok"
    if statuses:
        quality_status = max(statuses, key=lambda item: _STATUS_WEIGHT.get(item, 3))
    elif total_rows > 0 and output_rows == 0:
        quality_status = "failed"

    deduped_warnings = _dedupe_preserve_order(warning_messages)
    if quality_status == "ok" and deduped_warnings:
        quality_status = "warning"

    if output_rows == 0 and total_rows > 0:
        quality_status = "failed"

    return AnnouncementCleaningSummary(
        quality_status=quality_status,  # type: ignore[arg-type]
        total_rows=total_rows,
        output_rows=output_rows,
        dropped_rows=max(dropped_rows, 0),
        dropped_duplicate_rows=max(dropped_duplicate_rows, 0),
        warning_messages=deduped_warnings,
    )
