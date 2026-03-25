"""趋势与相对强弱因子。"""

from __future__ import annotations

from app.services.factor_service.base import FactorGroupResult, FactorMetric
from app.services.factor_service.preprocess import average_scores, linear_score, pct_change


def build_trend_group(closes: list[float]) -> FactorGroupResult:
    """构建趋势因子组。"""
    latest_close = closes[-1] if closes else None
    close_20 = closes[-21] if len(closes) >= 21 else None
    close_60 = closes[-61] if len(closes) >= 61 else None
    rolling_high = max(closes[-252:]) if closes else None

    return_20d = pct_change(latest_close, close_20)
    return_60d = pct_change(latest_close, close_60)
    distance_to_52w_high = None
    if latest_close is not None and rolling_high not in (None, 0):
        distance_to_52w_high = (latest_close / rolling_high) - 1.0

    metrics = [
        FactorMetric(
            factor_name="return_20d",
            raw_value=return_20d,
            normalized_score=linear_score(
                None if return_20d is None else return_20d * 100.0,
                -20.0,
                20.0,
            ),
            positive_signal=(
                None
                if return_20d is None
                else "20日收益率保持正向，短期相对强弱仍在改善"
            ),
            negative_signal=(
                None
                if return_20d is None
                else "20日收益率偏弱，短期相对强弱不足"
            ),
        ),
        FactorMetric(
            factor_name="return_60d",
            raw_value=return_60d,
            normalized_score=linear_score(
                None if return_60d is None else return_60d * 100.0,
                -30.0,
                35.0,
            ),
            positive_signal=(
                None
                if return_60d is None
                else "60日收益率较强，中期趋势延续性较好"
            ),
            negative_signal=(
                None
                if return_60d is None
                else "60日收益率偏弱，中期趋势支撑不足"
            ),
        ),
        FactorMetric(
            factor_name="distance_to_52w_high",
            raw_value=distance_to_52w_high,
            normalized_score=linear_score(
                None
                if distance_to_52w_high is None
                else abs(distance_to_52w_high) * 100.0,
                0.0,
                40.0,
                reverse=True,
            ),
            positive_signal=(
                None
                if distance_to_52w_high is None
                else "价格距离52周高点不远，强势结构仍在"
            ),
            negative_signal=(
                None
                if distance_to_52w_high is None
                else "价格距离52周高点较远，强势结构尚未恢复"
            ),
        ),
        FactorMetric(
            factor_name="relative_hs300_strength",
            raw_value=None,
            normalized_score=None,
            note="当前版本预留相对沪深300强弱接口，暂未纳入实际比较。",
        ),
        FactorMetric(
            factor_name="relative_industry_strength",
            raw_value=None,
            normalized_score=None,
            note="当前版本预留相对行业强弱接口，暂未纳入实际比较。",
        ),
    ]

    return FactorGroupResult(
        group_name="trend",
        metrics=metrics,
        score=average_scores(metric.normalized_score for metric in metrics),
    )
