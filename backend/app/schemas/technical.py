"""技术分析结构化输出 schema。"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class MovingAverageSnapshot(BaseModel):
    """均线快照。"""

    model_config = ConfigDict(extra="forbid")

    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma120: Optional[float] = None


class EmaSnapshot(BaseModel):
    """EMA 快照。"""

    model_config = ConfigDict(extra="forbid")

    ema12: Optional[float] = None
    ema26: Optional[float] = None


class MacdSnapshot(BaseModel):
    """MACD 快照。"""

    model_config = ConfigDict(extra="forbid")

    macd: Optional[float] = None
    signal: Optional[float] = None
    histogram: Optional[float] = None


class BollingerSnapshot(BaseModel):
    """布林带快照。"""

    model_config = ConfigDict(extra="forbid")

    middle: Optional[float] = None
    upper: Optional[float] = None
    lower: Optional[float] = None


class VolumeMetricsSnapshot(BaseModel):
    """成交量指标快照。"""

    model_config = ConfigDict(extra="forbid")

    volume_ma5: Optional[float] = None
    volume_ma20: Optional[float] = None
    volume_ratio_to_ma5: Optional[float] = None
    volume_ratio_to_ma20: Optional[float] = None


class TechnicalSnapshot(BaseModel):
    """最新交易日技术分析快照。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    as_of_date: date
    latest_close: float
    latest_volume: Optional[float] = None
    moving_averages: MovingAverageSnapshot
    ema: EmaSnapshot
    macd: MacdSnapshot
    rsi14: Optional[float] = None
    atr14: Optional[float] = None
    bollinger: BollingerSnapshot
    volume_metrics: VolumeMetricsSnapshot
    trend_state: Literal["up", "neutral", "down"]
    trend_score: int
    volatility_state: Literal["low", "normal", "high"]
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
