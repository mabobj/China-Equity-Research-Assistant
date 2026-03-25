"""因子预处理辅助函数。"""

from __future__ import annotations

from datetime import date
import math
from typing import Iterable, Optional, Sequence


def clamp_score(value: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(value))))


def clamp_optional_score(value: Optional[float]) -> Optional[float]:
    """将可选分数限制在 0 到 100。"""
    if value is None:
        return None
    return max(0.0, min(100.0, float(value)))


def linear_score(
    value: Optional[float],
    min_value: float,
    max_value: float,
    *,
    reverse: bool = False,
) -> Optional[float]:
    """将原始值线性映射到 0 到 100。"""
    if value is None:
        return None
    if math.isclose(max_value, min_value):
        return 50.0

    ratio = (float(value) - min_value) / (max_value - min_value)
    ratio = max(0.0, min(1.0, ratio))
    score = ratio * 100.0
    if reverse:
        score = 100.0 - score
    return clamp_optional_score(score)


def average_scores(values: Iterable[Optional[float]]) -> Optional[float]:
    """计算有效分数平均值。"""
    valid_values = [float(value) for value in values if value is not None]
    if not valid_values:
        return None
    return sum(valid_values) / len(valid_values)


def weighted_average_scores(
    values: Sequence[tuple[Optional[float], float]],
    *,
    default_score: float = 50.0,
) -> float:
    """计算加权平均分，忽略空值。"""
    weighted_sum = 0.0
    total_weight = 0.0
    for score, weight in values:
        if score is None or weight <= 0:
            continue
        weighted_sum += float(score) * weight
        total_weight += weight

    if total_weight <= 0:
        return default_score
    return weighted_sum / total_weight


def percent_like(value: Optional[float]) -> Optional[float]:
    """将可能是比例或百分比的值统一为百分数表达。"""
    if value is None:
        return None
    numeric_value = float(value)
    if abs(numeric_value) <= 1.5:
        return numeric_value * 100.0
    return numeric_value


def safe_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    """安全计算比值。"""
    if numerator is None or denominator is None:
        return None
    denominator_value = float(denominator)
    if math.isclose(denominator_value, 0.0):
        return None
    return float(numerator) / denominator_value


def pct_change(
    current_value: Optional[float],
    previous_value: Optional[float],
) -> Optional[float]:
    """计算涨跌幅，返回小数形式。"""
    ratio = safe_ratio(current_value, previous_value)
    if ratio is None:
        return None
    return ratio - 1.0


def annualized_volatility(closes: Sequence[Optional[float]]) -> Optional[float]:
    """基于收盘价序列估算年化波动率。"""
    numeric_closes = [float(value) for value in closes if value is not None]
    if len(numeric_closes) < 2:
        return None

    returns: list[float] = []
    for previous_value, current_value in zip(numeric_closes, numeric_closes[1:]):
        if math.isclose(previous_value, 0.0):
            continue
        returns.append((current_value / previous_value) - 1.0)

    if len(returns) < 2:
        return None

    mean_value = sum(returns) / len(returns)
    variance = sum((value - mean_value) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252.0)


def max_drawdown(closes: Sequence[Optional[float]]) -> Optional[float]:
    """计算最大回撤，返回正数比例。"""
    numeric_closes = [float(value) for value in closes if value is not None]
    if len(numeric_closes) < 2:
        return None

    peak = numeric_closes[0]
    max_drawdown_value = 0.0
    for value in numeric_closes:
        peak = max(peak, value)
        if math.isclose(peak, 0.0):
            continue
        drawdown = (peak - value) / peak
        max_drawdown_value = max(max_drawdown_value, drawdown)
    return max_drawdown_value


def days_between(later_date: date, earlier_date: date) -> int:
    """计算两个日期之间的自然日差。"""
    return max(0, (later_date - earlier_date).days)
