"""公告索引清洗入口。"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional, Sequence

from app.schemas.research_inputs import AnnouncementItem
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_service.cleaning.field_maps import map_announcement_row
from app.services.data_service.cleaning.quality import (
    aggregate_announcement_cleaning_summary,
)
from app.services.data_service.cleaning.rules import (
    build_announcement_dedupe_key,
    classify_announcement_type,
    validate_announcement_row,
)
from app.services.data_service.cleaning.types import (
    normalize_announcement_source,
    normalize_announcement_title,
    normalize_announcement_url,
    parse_announcement_publish_date,
)
from app.services.data_service.contracts.announcements import (
    CleanAnnouncementItem,
    CleanAnnouncementListResult,
)
from app.services.data_service.exceptions import InvalidSymbolError
from app.services.data_service.normalize import normalize_symbol

_STATUS_WEIGHT = {
    "ok": 0,
    "warning": 1,
    "degraded": 2,
    "failed": 3,
}


def clean_announcements(
    *,
    symbol: str,
    rows: Sequence[AnnouncementItem | Mapping[str, Any]],
    as_of_date: Optional[date] = None,
    default_source: Optional[str] = None,
    provider_used: Optional[str] = None,
    fallback_applied: bool = False,
    fallback_reason: Optional[str] = None,
    source_mode: Optional[str] = None,
    freshness_mode: Optional[str] = None,
) -> CleanAnnouncementListResult:
    """清洗公告索引列表并输出结构化结果。"""
    canonical_symbol = normalize_symbol(symbol)
    normalized_as_of_date = as_of_date or resolve_last_closed_trading_day()
    deduped: dict[str, CleanAnnouncementItem] = {}
    statuses: list[str] = []
    warning_messages: list[str] = []
    dropped_rows = 0
    dropped_duplicate_rows = 0
    observed_sources: list[str] = []

    for index, row in enumerate(rows):
        payload = _row_to_mapping(row, default_source=default_source)
        if payload is None:
            dropped_rows += 1
            warning_messages.append("row_{index}:unsupported_row_type".format(index=index))
            continue

        mapped = map_announcement_row(payload, default_source=default_source)
        normalized_symbol = _normalize_announcement_symbol(
            raw_symbol=mapped.get("symbol"),
            fallback_symbol=canonical_symbol,
        )
        title, title_coerced = normalize_announcement_title(mapped.get("title"))
        publish_date, publish_date_coerced = parse_announcement_publish_date(
            mapped.get("publish_date"),
        )
        normalized_source, source_coerced = normalize_announcement_source(
            mapped.get("source") or default_source or "unknown",
        )
        observed_sources.append(normalized_source)
        normalized_url, url_coerced = normalize_announcement_url(mapped.get("url"))
        announcement_type = classify_announcement_type(
            title=title,
            existing_type=_to_optional_text(mapped.get("announcement_type")),
        )
        announcement_subtype = _to_optional_text(mapped.get("announcement_subtype"))

        row_status, row_warnings, missing_fields = validate_announcement_row(
            title=title,
            publish_date=publish_date,
            url=normalized_url,
        )
        if publish_date_coerced:
            row_warnings.append("coerced_publish_date")
        coerced_fields: list[str] = []
        if title_coerced:
            coerced_fields.append("title")
        if publish_date_coerced:
            coerced_fields.append("publish_date")
        if source_coerced:
            coerced_fields.append("source")
        if url_coerced:
            coerced_fields.append("url")

        statuses.append(row_status)
        warning_messages.extend(
            "row_{index}:{warning}".format(index=index, warning=warning)
            for warning in row_warnings
        )
        if row_status == "failed" or publish_date is None:
            dropped_rows += 1
            continue

        dedupe_key = build_announcement_dedupe_key(
            symbol=normalized_symbol,
            publish_date=publish_date,
            normalized_title=title,
        )
        candidate = CleanAnnouncementItem(
            symbol=normalized_symbol,
            title=title,
            publish_date=publish_date,
            source=normalized_source,
            url=normalized_url,
            announcement_type=announcement_type,
            announcement_subtype=announcement_subtype,
            as_of_date=normalized_as_of_date,
            quality_status=row_status,  # type: ignore[arg-type]
            cleaning_warnings=list(dict.fromkeys(row_warnings)),
            missing_fields=list(dict.fromkeys(missing_fields)),
            coerced_fields=list(dict.fromkeys(coerced_fields)),
            provider_used=provider_used or normalized_source,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            source_mode=source_mode,
            freshness_mode=freshness_mode,
            dedupe_key=dedupe_key,
        )

        existing = deduped.get(dedupe_key)
        if existing is None:
            deduped[dedupe_key] = candidate
            continue

        dropped_duplicate_rows += 1
        warning_messages.append(
            "row_{index}:duplicate_dedupe_key".format(index=index),
        )
        deduped[dedupe_key] = _pick_better_announcement_item(existing, candidate)

    cleaned_items = sorted(
        deduped.values(),
        key=lambda item: (-item.publish_date.toordinal(), item.title),
    )
    summary = aggregate_announcement_cleaning_summary(
        statuses=statuses,
        warning_messages=warning_messages,
        total_rows=len(rows),
        output_rows=len(cleaned_items),
        dropped_rows=dropped_rows,
        dropped_duplicate_rows=dropped_duplicate_rows,
    )
    effective_provider = _resolve_provider_used(provider_used, observed_sources)
    return CleanAnnouncementListResult(
        symbol=canonical_symbol,
        items=cleaned_items,
        quality_status=summary.quality_status,
        cleaning_warnings=summary.warning_messages,
        dropped_rows=summary.dropped_rows,
        dropped_duplicate_rows=summary.dropped_duplicate_rows,
        as_of_date=normalized_as_of_date,
        provider_used=effective_provider,
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
        source_mode=source_mode,
        freshness_mode=freshness_mode,
        summary=summary,
    )


def _row_to_mapping(
    row: AnnouncementItem | Mapping[str, Any],
    *,
    default_source: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if isinstance(row, AnnouncementItem):
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


def _normalize_announcement_symbol(raw_symbol: Any, fallback_symbol: str) -> str:
    text = str(raw_symbol or "").strip()
    if text == "":
        return normalize_symbol(fallback_symbol)
    try:
        return normalize_symbol(text)
    except InvalidSymbolError:
        return normalize_symbol(fallback_symbol)


def _to_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def _pick_better_announcement_item(
    left: CleanAnnouncementItem,
    right: CleanAnnouncementItem,
) -> CleanAnnouncementItem:
    if left.url and not right.url:
        return left
    if right.url and not left.url:
        return right
    left_weight = _STATUS_WEIGHT.get(left.quality_status, 3)
    right_weight = _STATUS_WEIGHT.get(right.quality_status, 3)
    if right_weight < left_weight:
        return right
    if right_weight > left_weight:
        return left
    return right


def _resolve_provider_used(
    provider_used: Optional[str],
    observed_sources: list[str],
) -> Optional[str]:
    if provider_used:
        return provider_used
    deduped_sources = list(dict.fromkeys(source for source in observed_sources if source))
    if not deduped_sources:
        return None
    if len(deduped_sources) == 1:
        return deduped_sources[0]
    return "mixed"
