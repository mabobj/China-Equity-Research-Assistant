"""日线 bars 清洗入口。"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from app.schemas.market_data import DailyBar
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_service.cleaning.field_maps import map_daily_bar_row
from app.services.data_service.cleaning.quality import aggregate_cleaning_summary
from app.services.data_service.cleaning.rules import validate_bar_row
from app.services.data_service.cleaning.symbol import (
    normalize_daily_bar_symbol,
    parse_trading_date,
)
from app.services.data_service.cleaning.types import (
    normalize_amount,
    normalize_percent_value,
    normalize_volume,
    to_optional_float,
)
from app.services.data_service.contracts.bars import (
    CleanDailyBar,
    CleanDailyBarsResult,
)


def clean_daily_bars(
    *,
    symbol: str,
    rows: Sequence[DailyBar | Mapping[str, Any]],
    as_of_date: date | None = None,
    default_source: str | None = None,
) -> CleanDailyBarsResult:
    """清洗并标准化日线数据。"""
    normalized_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
    normalized_items: dict[tuple[str, date], CleanDailyBar] = {}
    status_bucket: list[str] = []
    warnings: list[str] = []
    dropped_rows = 0
    dropped_duplicate_rows = 0

    for index, row in enumerate(rows):
        raw_item = _row_to_mapping(row, default_source=default_source)
        if raw_item is None:
            dropped_rows += 1
            warnings.append(f"row_{index}:unsupported_row_type")
            continue

        normalized_symbol = normalize_daily_bar_symbol(
            str(raw_item.get("symbol") or ""),
            symbol,
        )
        trade_date = parse_trading_date(raw_item.get("trade_date"))
        if trade_date is None:
            dropped_rows += 1
            warnings.append(f"row_{index}:invalid_trade_date")
            continue

        source = str(raw_item.get("source") or default_source or "unknown").strip().lower()
        open_price, open_coerced = to_optional_float(raw_item.get("open"))
        high_price, high_coerced = to_optional_float(raw_item.get("high"))
        low_price, low_coerced = to_optional_float(raw_item.get("low"))
        close_price, close_coerced = to_optional_float(raw_item.get("close"))
        volume, volume_coerced = to_optional_float(raw_item.get("volume"))
        amount, amount_coerced = to_optional_float(raw_item.get("amount"))
        turnover_rate, turnover_coerced = to_optional_float(raw_item.get("turnover_rate"))
        pct_change, pct_change_coerced = to_optional_float(raw_item.get("pct_change"))

        volume = normalize_volume(volume, source=source)
        amount = normalize_amount(amount, source=source)
        turnover_rate = normalize_percent_value(turnover_rate)
        pct_change = normalize_percent_value(pct_change)

        row_status, row_warnings = validate_bar_row(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            amount=amount,
        )
        status_bucket.append(row_status)
        warnings.extend([f"row_{index}:{item}" for item in row_warnings])

        if row_status == "failed":
            dropped_rows += 1
            continue

        coerced_fields = [
            field_name
            for field_name, coerced in (
                ("open", open_coerced),
                ("high", high_coerced),
                ("low", low_coerced),
                ("close", close_coerced),
                ("volume", volume_coerced),
                ("amount", amount_coerced),
                ("turnover_rate", turnover_coerced),
                ("pct_change", pct_change_coerced),
            )
            if coerced
        ]
        missing_fields = [
            field_name
            for field_name, value in (
                ("open", open_price),
                ("high", high_price),
                ("low", low_price),
                ("close", close_price),
                ("volume", volume),
                ("amount", amount),
            )
            if value is None
        ]

        candidate = CleanDailyBar(
            symbol=normalized_symbol,
            trade_date=trade_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            amount=amount,
            turnover_rate=turnover_rate,
            pct_change=pct_change,
            adjustment_mode=getattr(row, "adjustment_mode", "raw") if isinstance(row, DailyBar) else str(raw_item.get("adjustment_mode") or "raw"),
            trading_status=(
                getattr(row, "trading_status", None)
                if isinstance(row, DailyBar)
                else raw_item.get("trading_status")
            ),
            corporate_action_flags=(
                list(getattr(row, "corporate_action_flags", []))
                if isinstance(row, DailyBar)
                else list(raw_item.get("corporate_action_flags") or [])
            ),
            source=source,
            as_of_date=normalized_as_of_date,
            quality_status=row_status,  # type: ignore[arg-type]
            cleaning_warnings=row_warnings,
            coerced_fields=coerced_fields,
            missing_fields=missing_fields,
        )
        dedupe_key = (candidate.symbol, candidate.trade_date)
        if dedupe_key in normalized_items:
            existing = normalized_items[dedupe_key]
            if _same_bar_content(existing, candidate):
                dropped_duplicate_rows += 1
                dropped_rows += 1
                warnings.append(f"row_{index}:duplicate_row")
                continue
            dropped_duplicate_rows += 1
            dropped_rows += 1
            warnings.append(f"row_{index}:duplicate_conflict_keep_latest")
        normalized_items[dedupe_key] = candidate

    clean_bars = sorted(normalized_items.values(), key=lambda item: item.trade_date)
    summary = aggregate_cleaning_summary(
        statuses=status_bucket,
        warning_messages=warnings,
        total_rows=len(rows),
        output_rows=len(clean_bars),
        dropped_rows=dropped_rows,
        dropped_duplicate_rows=dropped_duplicate_rows,
    )
    return CleanDailyBarsResult(bars=clean_bars, summary=summary)


def _row_to_mapping(
    row: DailyBar | Mapping[str, Any],
    *,
    default_source: str | None,
) -> dict[str, Any] | None:
    if isinstance(row, DailyBar):
        payload = row.model_dump(mode="python")
        if "source" not in payload and default_source is not None:
            payload["source"] = default_source
        return payload
    if isinstance(row, Mapping):
        return map_daily_bar_row(row, default_source=default_source)
    return None


def _same_bar_content(left: CleanDailyBar, right: CleanDailyBar) -> bool:
    return (
        left.open == right.open
        and left.high == right.high
        and left.low == right.low
        and left.close == right.close
        and left.volume == right.volume
        and left.amount == right.amount
        and left.turnover_rate == right.turnover_rate
        and left.pct_change == right.pct_change
    )
