"""provider 原始字段映射到统一 bars 字段。"""

from __future__ import annotations

from typing import Any, Mapping

_DAILY_BAR_FIELD_ALIASES = {
    "symbol": "symbol",
    "code": "symbol",
    "ts_code": "symbol",
    "date": "trade_date",
    "trade_date": "trade_date",
    "datetime": "trade_date",
    "日期": "trade_date",
    "open": "open",
    "开盘": "open",
    "high": "high",
    "最高": "high",
    "low": "low",
    "最低": "low",
    "close": "close",
    "收盘": "close",
    "volume": "volume",
    "vol": "volume",
    "成交量": "volume",
    "amount": "amount",
    "amt": "amount",
    "成交额": "amount",
    "turnover_rate": "turnover_rate",
    "turnover": "turnover_rate",
    "换手率": "turnover_rate",
    "pct_change": "pct_change",
    "涨跌幅": "pct_change",
    "source": "source",
}


def map_daily_bar_row(
    row: Mapping[str, Any],
    *,
    default_source: str | None = None,
) -> dict[str, Any]:
    """把原始 row 映射为统一键名。"""
    mapped: dict[str, Any] = {}
    for raw_key, raw_value in row.items():
        canonical_key = _DAILY_BAR_FIELD_ALIASES.get(str(raw_key).strip().lower())
        if canonical_key is None:
            canonical_key = _DAILY_BAR_FIELD_ALIASES.get(str(raw_key).strip())
        if canonical_key is None:
            continue
        mapped[canonical_key] = raw_value
    if default_source is not None and "source" not in mapped:
        mapped["source"] = default_source
    return mapped
