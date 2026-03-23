"""技术指标计算测试。"""

from datetime import date, timedelta

import pytest
import pandas as pd

from app.services.feature_service.indicators import add_indicators


def test_add_indicators_generates_expected_latest_values() -> None:
    """指标引擎应生成关键指标列和合理结果。"""
    frame = _build_indicator_frame(length=40)

    enriched = add_indicators(frame)
    latest = enriched.iloc[-1]

    assert latest["ma5"] == pytest.approx(sum(range(36, 41)) / 5.0)
    assert latest["ma20"] == pytest.approx(sum(range(21, 41)) / 20.0)
    assert latest["volume_ma5"] == pytest.approx(sum(float(index * 1000) for index in range(36, 41)) / 5.0)
    assert latest["ema12"] is not None
    assert latest["ema26"] is not None
    assert latest["macd"] > 0
    assert latest["macd_signal"] > 0
    assert latest["rsi14"] > 50
    assert latest["atr14"] > 0
    assert latest["bollinger_upper"] > latest["bollinger_middle"] > latest["bollinger_lower"]


def _build_indicator_frame(length: int) -> pd.DataFrame:
    """构造用于指标测试的日线数据。"""
    rows = []
    start = date(2024, 1, 1)
    for index in range(1, length + 1):
        rows.append(
            {
                "trade_date": pd.Timestamp(start + timedelta(days=index - 1)),
                "open": float(index) - 0.5,
                "high": float(index) + 1.0,
                "low": float(index) - 1.0,
                "close": float(index),
                "volume": float(index * 1000),
                "amount": float(index * 10000),
            }
        )

    return pd.DataFrame(rows)
