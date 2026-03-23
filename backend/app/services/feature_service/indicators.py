"""技术指标计算。"""

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """为日线数据添加基础技术指标列。"""
    data = frame.copy()

    for window in (5, 10, 20, 60, 120):
        data["ma{window}".format(window=window)] = _rolling_mean(
            data["close"],
            window=window,
        )

    data["ema12"] = _ema(data["close"], span=12)
    data["ema26"] = _ema(data["close"], span=26)
    data["macd"] = data["ema12"] - data["ema26"]
    data["macd_signal"] = _ema(data["macd"], span=9)
    data["macd_histogram"] = data["macd"] - data["macd_signal"]
    data["rsi14"] = _rsi(data["close"], window=14)
    data["atr14"] = _atr(data, window=14)

    boll_middle = _rolling_mean(data["close"], window=20)
    boll_std = data["close"].rolling(window=20, min_periods=20).std(ddof=0)
    data["bollinger_middle"] = boll_middle
    data["bollinger_upper"] = boll_middle + (2.0 * boll_std)
    data["bollinger_lower"] = boll_middle - (2.0 * boll_std)

    data["volume_ma5"] = _rolling_mean(data["volume"], window=5)
    data["volume_ma20"] = _rolling_mean(data["volume"], window=20)
    return data


def _rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """计算滚动均值。"""
    return series.rolling(window=window, min_periods=window).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    """计算指数移动均线。"""
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _rsi(series: pd.Series, window: int) -> pd.Series:
    """计算 RSI。"""
    delta = series.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)

    average_gain = gains.ewm(
        alpha=1.0 / float(window),
        adjust=False,
        min_periods=window,
    ).mean()
    average_loss = losses.ewm(
        alpha=1.0 / float(window),
        adjust=False,
        min_periods=window,
    ).mean()

    relative_strength = average_gain / average_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + relative_strength))
    return rsi.fillna(100.0)


def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
    """计算 ATR。"""
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1.0 / float(window),
        adjust=False,
        min_periods=window,
    ).mean()


def latest_value(series: pd.Series) -> Optional[float]:
    """获取序列最后一个非空值。"""
    values = series.dropna()
    if values.empty:
        return None
    return float(values.iloc[-1])


def latest_optional_float(value: object) -> Optional[float]:
    """将标量转换为可选浮点数。"""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clamp_score(value: float, lower: int = 0, upper: int = 100) -> int:
    """将分数限制在给定区间。"""
    return int(max(lower, min(upper, round(value))))


def available_values(values: Iterable[Optional[float]]) -> list[float]:
    """过滤空值。"""
    return [value for value in values if value is not None]
