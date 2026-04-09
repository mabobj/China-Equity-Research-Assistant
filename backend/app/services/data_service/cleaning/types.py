"""数据清洗的类型与单位归一化工具。"""

from __future__ import annotations

from datetime import date
import math
import re
from typing import Any, Optional, Tuple

from app.services.common.text_normalization import normalize_display_text
from app.services.data_service.normalize import (
    normalize_amount_to_yuan,
    normalize_provider_name,
    normalize_volume_to_shares,
    parse_provider_date,
)

_MISSING_STRINGS = {"", "--", "-", "none", "null", "nan", "na", "n/a", "—"}

_SOURCE_ALIASES = {
    "akshare_api": "akshare",
    "aksharepro": "akshare",
    "巨潮资讯": "cninfo",
    "juchao": "cninfo",
    "cninfo.com.cn": "cninfo",
    "eastmoney_api": "eastmoney",
    "东方财富": "eastmoney",
    "tdx-api": "tdx_api",
    "tdxapi": "tdx_api",
}


def is_missing_value(value: Any) -> bool:
    """判断是否为空值。"""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in _MISSING_STRINGS:
        return True
    return False


def to_optional_float(value: Any) -> Tuple[float | None, bool]:
    """转换为浮点数，并返回是否发生了强制转换。"""
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
    """统一 volume 到股。"""
    return normalize_volume_to_shares(value, source=_normalize_source(source))


def normalize_amount(value: float | None, *, source: str) -> float | None:
    """统一 amount 到元。"""
    return normalize_amount_to_yuan(value, source=_normalize_source(source))


def normalize_percent_value(value: float | None) -> float | None:
    """统一百分比口径，输出 3.5 表示 3.5%。"""
    if value is None:
        return None
    if value != 0 and -1.0 < value < 1.0:
        return value * 100.0
    return value


def parse_financial_amount_to_yuan(value: Any) -> Tuple[float | None, bool]:
    """把财务金额统一解析为元，并返回是否发生了强制转换。"""
    if is_missing_value(value):
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False

    raw_text = str(value).strip().replace(",", "").replace("，", "")
    if raw_text == "":
        return None, False

    multiplier = 1.0
    coerced = False
    normalized_text = raw_text
    if normalized_text.endswith("亿元"):
        multiplier = 100000000.0
        normalized_text = normalized_text[:-2]
        coerced = True
    elif normalized_text.endswith("亿"):
        multiplier = 100000000.0
        normalized_text = normalized_text[:-1]
        coerced = True
    elif normalized_text.endswith("万元"):
        multiplier = 10000.0
        normalized_text = normalized_text[:-2]
        coerced = True
    elif normalized_text.endswith("万"):
        multiplier = 10000.0
        normalized_text = normalized_text[:-1]
        coerced = True
    elif normalized_text.endswith("元"):
        normalized_text = normalized_text[:-1]
        coerced = True

    normalized_text = normalized_text.strip()
    if normalized_text == "":
        return None, coerced

    try:
        return float(normalized_text) * multiplier, coerced
    except ValueError:
        return None, False


def parse_financial_percent(value: Any) -> Tuple[float | None, bool]:
    """把财务比率统一解析为百分数口径。"""
    if is_missing_value(value):
        return None, False
    if isinstance(value, (int, float)):
        normalized = normalize_percent_value(float(value))
        return normalized, normalized != float(value)

    text = str(value).strip().replace(",", "").replace("，", "")
    if text == "":
        return None, False

    has_percent = text.endswith("%")
    numeric_text = text[:-1] if has_percent else text
    numeric_text = numeric_text.strip()
    if numeric_text == "":
        return None, has_percent

    try:
        numeric_value = float(numeric_text)
    except ValueError:
        return None, False

    if has_percent:
        return numeric_value, True
    normalized = normalize_percent_value(numeric_value)
    return normalized, normalized != numeric_value


def normalize_announcement_title(value: Any) -> tuple[str, bool]:
    """统一公告标题文本，不改写语义。"""
    if is_missing_value(value):
        return "", False
    raw_text = str(value)
    normalized = normalize_display_text(raw_text).replace("\r", " ").replace("\n", " ")
    normalized = " ".join(normalized.split())
    return normalized, normalized != raw_text


def parse_announcement_publish_date(value: Any) -> tuple[date | None, bool]:
    """统一公告发布日期。"""
    if is_missing_value(value):
        return None, False
    parsed = parse_provider_date(value)
    return parsed, parsed is not None and not isinstance(value, date)


def normalize_announcement_source(value: Any) -> tuple[str, bool]:
    """统一公告来源值。"""
    if is_missing_value(value):
        return "unknown", False
    raw_text = str(value).strip()
    normalized = _normalize_source(raw_text)
    return normalized, normalized != raw_text


def normalize_announcement_url(value: Any) -> tuple[str | None, bool]:
    """统一公告 URL，空串转 None。"""
    if is_missing_value(value):
        return None, False
    raw_text = str(value).strip()
    normalized = raw_text or None
    return normalized, normalized != raw_text


def parse_financial_report_period_and_type(
    period_value: Any,
    report_type_value: Any = None,
) -> tuple[Optional[date], str, bool]:
    """解析报告期与报告类型。"""
    explicit_report_type = _normalize_report_type_text(report_type_value)
    if explicit_report_type is not None and explicit_report_type != "unknown":
        report_period = _parse_report_period_value(period_value, explicit_report_type)
        return report_period, explicit_report_type, True

    text = _normalize_text_value(period_value)
    if text is None:
        if explicit_report_type is not None:
            return None, explicit_report_type, True
        return None, "unknown", False

    upper_text = text.upper()
    if "TTM" in upper_text:
        return None, "ttm", True

    quarter_match = re.match(r"^(\d{4})\s*[-/ ]?Q([1-4])$", upper_text)
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = quarter_match.group(2)
        return _quarter_to_period(year, quarter), _quarter_to_type(quarter), True

    year_report_match = re.match(r"^(\d{4})\s*年报$", text)
    if year_report_match:
        year = int(year_report_match.group(1))
        return date(year, 12, 31), "annual", True

    chinese_quarter_match = re.match(
        r"^(\d{4})\s*(?:年\s*)?(一季报|二季报|三季报|半年报|中报)$",
        text,
    )
    if chinese_quarter_match:
        year = int(chinese_quarter_match.group(1))
        label = chinese_quarter_match.group(2)
        if label == "一季报":
            return date(year, 3, 31), "q1", True
        if label in {"二季报", "半年报", "中报"}:
            return date(year, 6, 30), "half", True
        if label == "三季报":
            return date(year, 9, 30), "q3", True

    period = _parse_date_text(text)
    if period is not None:
        return period, _infer_report_type_from_period(period), True
    return None, "unknown", False


def _normalize_source(source: str) -> str:
    normalized = normalize_provider_name(source)
    if normalized in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[normalized]
    if normalized.startswith("cninfo"):
        return "cninfo"
    if normalized.startswith("eastmoney"):
        return "eastmoney"
    if normalized.startswith("akshare"):
        return "akshare"
    return normalized


def _normalize_text_value(value: Any) -> Optional[str]:
    if is_missing_value(value):
        return None
    text = normalize_display_text(str(value).strip())
    return text or None


def _normalize_report_type_text(value: Any) -> Optional[str]:
    text = _normalize_text_value(value)
    if text is None:
        return None
    normalized = text.strip().lower()
    mapping = {
        "annual": "annual",
        "yearly": "annual",
        "year": "annual",
        "q1": "q1",
        "quarter1": "q1",
        "half": "half",
        "h1": "half",
        "midyear": "half",
        "q3": "q3",
        "quarter3": "q3",
        "ttm": "ttm",
        "unknown": "unknown",
        "年报": "annual",
        "一季报": "q1",
        "半年报": "half",
        "中报": "half",
        "三季报": "q3",
    }
    return mapping.get(normalized)


def _parse_report_period_value(period_value: Any, report_type: str) -> Optional[date]:
    text = _normalize_text_value(period_value)
    if text is None:
        return None
    period = _parse_date_text(text)
    if period is not None:
        return period

    year_match = re.match(r"^(\d{4})$", text)
    if year_match:
        year = int(year_match.group(1))
        if report_type == "annual":
            return date(year, 12, 31)
        if report_type == "q1":
            return date(year, 3, 31)
        if report_type == "half":
            return date(year, 6, 30)
        if report_type == "q3":
            return date(year, 9, 30)
    return None


def _parse_date_text(text: str) -> Optional[date]:
    return parse_provider_date(text)


def _infer_report_type_from_period(period: date) -> str:
    if period.month == 3 and period.day == 31:
        return "q1"
    if period.month == 6 and period.day == 30:
        return "half"
    if period.month == 9 and period.day == 30:
        return "q3"
    if period.month == 12 and period.day == 31:
        return "annual"
    return "unknown"


def _quarter_to_period(year: int, quarter: str) -> date:
    if quarter == "1":
        return date(year, 3, 31)
    if quarter == "2":
        return date(year, 6, 30)
    if quarter == "3":
        return date(year, 9, 30)
    return date(year, 12, 31)


def _quarter_to_type(quarter: str) -> str:
    if quarter == "1":
        return "q1"
    if quarter == "2":
        return "half"
    if quarter == "3":
        return "q3"
    return "annual"
