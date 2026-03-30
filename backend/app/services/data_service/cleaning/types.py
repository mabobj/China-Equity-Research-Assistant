"""bars 清洗类型转换与单位归一化。"""

from __future__ import annotations

import math
from typing import Any, Tuple

_MISSING_STRINGS = {"", "--", "—", "none", "null", "nan", "na", "n/a"}

_VOLUME_UNIT_BY_SOURCE = {
    "akshare": "hand",
    "baostock": "share",
    "mootdx": "hand",
}

_AMOUNT_UNIT_BY_SOURCE = {
    "akshare": "yuan",
    "baostock": "yuan",
    "mootdx": "yuan",
}


def is_missing_value(value: Any) -> bool:
    """判断是否缺失值。"""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in _MISSING_STRINGS:
        return True
    return False


def to_optional_float(value: Any) -> Tuple[float | None, bool]:
    """转换到浮点；返回 (值, 是否发生强制转换)。"""
    if is_missing_value(value):
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False

    text = str(value).strip().replace(",", "")
    if text == "":
        return None, False
    try:
        return float(text), True
    except ValueError:
        return None, False


def normalize_volume(value: float | None, *, source: str) -> float | None:
    """统一 volume 到“股”。"""
    if value is None:
        return None
    unit = _VOLUME_UNIT_BY_SOURCE.get(source, "share")
    if unit == "hand":
        return value * 100.0
    return value


def normalize_amount(value: float | None, *, source: str) -> float | None:
    """统一 amount 到“元”。"""
    if value is None:
        return None
    unit = _AMOUNT_UNIT_BY_SOURCE.get(source, "yuan")
    if unit == "wan_yuan":
        return value * 10000.0
    return value


def normalize_percent_value(value: float | None) -> float | None:
    """统一百分比口径：默认输出 3.5 表示 3.5%。"""
    if value is None:
        return None
    if value != 0 and -1.0 < value < 1.0:
        return value * 100.0
    return value
