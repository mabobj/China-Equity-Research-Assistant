"""低波动与风险效率因子。"""

from __future__ import annotations

from app.schemas.technical import TechnicalSnapshot
from app.services.factor_service.base import FactorGroupResult, FactorMetric
from app.services.factor_service.preprocess import (
    average_scores,
    annualized_volatility,
    linear_score,
    max_drawdown,
    safe_ratio,
)


def build_low_vol_group(
    closes: list[float],
    technical_snapshot: TechnicalSnapshot,
) -> FactorGroupResult:
    """构建低波动因子组。"""
    vol_20 = annualized_volatility(closes[-20:]) if len(closes) >= 20 else None
    vol_60 = annualized_volatility(closes[-60:]) if len(closes) >= 60 else None
    atr_to_close = None
    if technical_snapshot.atr14 is not None and technical_snapshot.latest_close > 0:
        atr_to_close = safe_ratio(technical_snapshot.atr14, technical_snapshot.latest_close)
    drawdown_60 = max_drawdown(closes[-60:]) if len(closes) >= 60 else None

    metrics = [
        FactorMetric(
            factor_name="volatility_20d",
            raw_value=vol_20,
            normalized_score=linear_score(
                None if vol_20 is None else vol_20 * 100.0,
                10.0,
                60.0,
                reverse=True,
            ),
            positive_signal="20日波动率较低，短期波动相对可控",
            negative_signal="20日波动率偏高，短期波动风险较大",
        ),
        FactorMetric(
            factor_name="volatility_60d",
            raw_value=vol_60,
            normalized_score=linear_score(
                None if vol_60 is None else vol_60 * 100.0,
                10.0,
                70.0,
                reverse=True,
            ),
            positive_signal="60日波动率较低，中期风险效率较好",
            negative_signal="60日波动率偏高，中期风险效率一般",
        ),
        FactorMetric(
            factor_name="atr_to_close",
            raw_value=atr_to_close,
            normalized_score=linear_score(
                None if atr_to_close is None else atr_to_close * 100.0,
                1.0,
                8.0,
                reverse=True,
            ),
            positive_signal="ATR/收盘价比值较低，价格波动相对平稳",
            negative_signal="ATR/收盘价比值偏高，价格波动偏大",
        ),
        FactorMetric(
            factor_name="max_drawdown_60d",
            raw_value=drawdown_60,
            normalized_score=linear_score(
                None if drawdown_60 is None else drawdown_60 * 100.0,
                5.0,
                35.0,
                reverse=True,
            ),
            positive_signal="近60日最大回撤较小，回撤控制尚可",
            negative_signal="近60日最大回撤偏大，下行风险需要关注",
        ),
    ]

    return FactorGroupResult(
        group_name="low_vol",
        metrics=metrics,
        score=average_scores(metric.normalized_score for metric in metrics),
    )
