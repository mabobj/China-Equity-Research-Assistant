"""支撑位与压力位识别。"""

from typing import Optional

import pandas as pd


def detect_support_resistance(
    frame: pd.DataFrame,
    window: int = 20,
) -> tuple[Optional[float], Optional[float]]:
    """基于近期区间高低点识别支撑位与压力位。"""
    if frame.empty:
        return None, None

    recent = frame.tail(window)
    support = _series_min(recent["low"])
    resistance = _series_max(recent["high"])
    return support, resistance


def _series_min(series: pd.Series) -> Optional[float]:
    """获取序列最小值。"""
    values = series.dropna()
    if values.empty:
        return None
    return float(values.min())


def _series_max(series: pd.Series) -> Optional[float]:
    """获取序列最大值。"""
    values = series.dropna()
    if values.empty:
        return None
    return float(values.max())
