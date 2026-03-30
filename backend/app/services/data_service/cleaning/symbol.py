"""symbol / 日期规范化工具。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.data_service.exceptions import InvalidSymbolError
from app.services.data_service.normalize import normalize_symbol


def normalize_daily_bar_symbol(raw_symbol: str, fallback_symbol: str) -> str:
    """优先使用行内 symbol，失败时回退到请求 symbol。"""
    target = (raw_symbol or "").strip()
    if target == "":
        return normalize_symbol(fallback_symbol)
    try:
        return normalize_symbol(target)
    except InvalidSymbolError:
        return normalize_symbol(fallback_symbol)


def parse_trading_date(value: Any) -> date | None:
    """解析交易日字段。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    patterns = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S")
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None
