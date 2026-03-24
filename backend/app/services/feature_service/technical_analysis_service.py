"""技术分析快照服务。"""

from typing import Optional

import pandas as pd

from app.schemas.market_data import DailyBar
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.data_service.exceptions import (
    DataNotFoundError,
    InsufficientDataError,
)
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.normalize import normalize_symbol
from app.services.feature_service.indicators import add_indicators, latest_optional_float
from app.services.feature_service.levels import detect_support_resistance
from app.services.feature_service.trend import evaluate_trend
from app.services.feature_service.volatility import evaluate_volatility_state


class TechnicalAnalysisService:
    """基于日线数据构建技术分析快照。"""

    def __init__(self, market_data_service: MarketDataService) -> None:
        self._market_data_service = market_data_service

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TechnicalSnapshot:
        """获取最新交易日的技术分析快照。"""
        canonical_symbol = normalize_symbol(symbol)
        daily_bar_response = self._market_data_service.get_daily_bars(
            symbol=canonical_symbol,
            start_date=start_date,
            end_date=end_date,
        )
        return self.build_snapshot_from_bars(
            symbol=canonical_symbol,
            bars=daily_bar_response.bars,
        )

    def build_snapshot_from_bars(
        self,
        symbol: str,
        bars: list[DailyBar],
    ) -> TechnicalSnapshot:
        """基于已加载的日线数据生成技术快照。"""
        canonical_symbol = normalize_symbol(symbol)
        if not bars:
            raise DataNotFoundError(
                "未找到可用于技术分析的日线数据：{symbol}。".format(
                    symbol=canonical_symbol,
                ),
            )

        frame = _build_price_frame(bars)
        if len(frame) < 30:
            raise InsufficientDataError(
                "技术分析至少需要 30 根有效日线数据，当前只有 {count} 根。".format(
                    count=len(frame),
                ),
            )

        enriched = add_indicators(frame)
        latest_row = enriched.iloc[-1]
        latest_map = {
            column: latest_optional_float(latest_row.get(column))
            for column in enriched.columns
        }
        trend_state, trend_score = evaluate_trend(latest_map)
        volatility_state = evaluate_volatility_state(latest_map)
        support_level, resistance_level = detect_support_resistance(enriched)

        latest_close = latest_map.get("close")
        if latest_close is None:
            raise InsufficientDataError("最新交易日缺少收盘价，无法生成技术快照。")

        return TechnicalSnapshot(
            symbol=canonical_symbol,
            as_of_date=latest_row["trade_date"].date(),
            latest_close=latest_close,
            latest_volume=latest_map.get("volume"),
            moving_averages=MovingAverageSnapshot(
                ma5=latest_map.get("ma5"),
                ma10=latest_map.get("ma10"),
                ma20=latest_map.get("ma20"),
                ma60=latest_map.get("ma60"),
                ma120=latest_map.get("ma120"),
            ),
            ema=EmaSnapshot(
                ema12=latest_map.get("ema12"),
                ema26=latest_map.get("ema26"),
            ),
            macd=MacdSnapshot(
                macd=latest_map.get("macd"),
                signal=latest_map.get("macd_signal"),
                histogram=latest_map.get("macd_histogram"),
            ),
            rsi14=latest_map.get("rsi14"),
            atr14=latest_map.get("atr14"),
            bollinger=BollingerSnapshot(
                middle=latest_map.get("bollinger_middle"),
                upper=latest_map.get("bollinger_upper"),
                lower=latest_map.get("bollinger_lower"),
            ),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma5=latest_map.get("volume_ma5"),
                volume_ma20=latest_map.get("volume_ma20"),
                volume_ratio_to_ma5=_safe_ratio(
                    latest_map.get("volume"),
                    latest_map.get("volume_ma5"),
                ),
                volume_ratio_to_ma20=_safe_ratio(
                    latest_map.get("volume"),
                    latest_map.get("volume_ma20"),
                ),
            ),
            trend_state=trend_state,
            trend_score=trend_score,
            volatility_state=volatility_state,
            support_level=support_level,
            resistance_level=resistance_level,
        )


def _build_price_frame(bars: list[DailyBar]) -> pd.DataFrame:
    """将日线 bars 转成技术分析使用的 DataFrame。"""
    rows = []
    for bar in bars:
        rows.append(
            {
                "trade_date": pd.Timestamp(bar.trade_date),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "amount": bar.amount,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.sort_values("trade_date").drop_duplicates(
        subset=["trade_date"],
        keep="last",
    )
    for column in ("open", "high", "low", "close", "volume", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(
        subset=["trade_date", "high", "low", "close"],
    ).reset_index(drop=True)
    return frame


def _safe_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    """安全计算比值。"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator / denominator)
