"""Initial screener process metrics and atomic factor builder."""

from __future__ import annotations

from datetime import date, datetime
from math import sqrt
from typing import Optional

import pandas as pd

from app.schemas.market_data import DailyBar
from app.schemas.screener_factors import (
    AtrPctState,
    DistanceState,
    LiquidityRatioState,
    LiquidityState,
    RangeState,
    ScreenerAtomicFactors,
    ScreenerCrossSectionFactors,
    ScreenerFactorSnapshot,
    ScreenerProcessMetrics,
    ScreenerRawInputs,
    build_screener_dataset_version,
)
from app.services.data_service.exceptions import InsufficientDataError
from app.services.data_service.normalize import normalize_symbol
from app.services.feature_service.indicators import (
    add_indicators,
    build_price_frame_from_bars,
    latest_optional_float,
)


class ScreenerFactorService:
    """Build deterministic screener process metrics and atomic factors from daily bars."""

    def build_snapshot_from_bars(
        self,
        *,
        symbol: str,
        bars: list[DailyBar],
        name: Optional[str] = None,
        market: Optional[str] = None,
        board: Optional[str] = None,
        industry: Optional[str] = None,
        list_date: Optional[date] = None,
        latest_trade_date: Optional[date] = None,
        list_status: Optional[str] = None,
        is_st: Optional[bool] = None,
        is_suspended: Optional[bool] = None,
        provider_used: Optional[str] = None,
        source_mode: Optional[str] = None,
        freshness_mode: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        warning_messages: Optional[list[str]] = None,
    ) -> ScreenerFactorSnapshot:
        canonical_symbol = normalize_symbol(symbol)
        frame = build_price_frame_from_bars(bars)
        if len(frame) < 60:
            raise InsufficientDataError(
                "构建初筛因子快照至少需要 60 根有效日线数据，当前不足。",
            )

        enriched = _add_screener_metrics(add_indicators(frame))
        latest_row = enriched.iloc[-1]
        latest_map = {
            column: latest_optional_float(latest_row.get(column))
            for column in enriched.columns
        }
        as_of_date = latest_row["trade_date"].date()
        process_metrics = _build_process_metrics(latest_map)
        raw_inputs = ScreenerRawInputs(
            symbol=canonical_symbol,
            name=name,
            market=market,
            board=board,
            industry=industry,
            list_date=list_date,
            latest_trade_date=latest_trade_date or as_of_date,
            list_status=list_status,
            is_st=is_st,
            is_suspended=is_suspended,
            bars_count=len(frame),
            latest_close=latest_map.get("close"),
            latest_volume=latest_map.get("volume"),
            latest_amount=latest_map.get("amount"),
        )
        atomic_factors = _build_atomic_factors(
            process_metrics=process_metrics,
            raw_inputs=raw_inputs,
            as_of_date=as_of_date,
        )

        return ScreenerFactorSnapshot(
            symbol=canonical_symbol,
            as_of_date=as_of_date,
            dataset_version=build_screener_dataset_version(
                dataset="screener_factor_snapshot_daily",
                as_of_date=as_of_date,
                symbol=canonical_symbol,
            ),
            generated_at=generated_at,
            provider_used=provider_used,
            source_mode=source_mode,
            freshness_mode=freshness_mode,
            raw_inputs=raw_inputs,
            process_metrics=process_metrics,
            atomic_factors=atomic_factors,
            cross_section_factors=ScreenerCrossSectionFactors(),
            warning_messages=list(warning_messages or []),
        )


def _add_screener_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["ma20_prev_5"] = data["ma20"].shift(5)
    data["ma60_prev_10"] = data["ma60"].shift(10)
    data["ma20_slope"] = _safe_ratio_series(data["ma20"], data["ma20_prev_5"]) - 1.0
    data["ma60_slope"] = _safe_ratio_series(data["ma60"], data["ma60_prev_10"]) - 1.0
    data["rolling_low_60"] = data["low"].rolling(window=60, min_periods=60).min()
    data["rolling_high_60"] = data["high"].rolling(window=60, min_periods=60).max()
    data["close_percentile_60d"] = (
        (data["close"] - data["rolling_low_60"])
        / (data["rolling_high_60"] - data["rolling_low_60"]).replace(0.0, pd.NA)
    )
    data["close_prev_20"] = data["close"].shift(20)
    data["close_prev_60"] = data["close"].shift(60)
    data["return_20d"] = _safe_ratio_series(data["close"], data["close_prev_20"]) - 1.0
    data["return_60d"] = _safe_ratio_series(data["close"], data["close_prev_60"]) - 1.0
    data["atr20"] = _atr(data, window=20)
    data["atr20_pct"] = data["atr20"] / data["close"].replace(0.0, pd.NA)
    data["rolling_low_20"] = data["low"].rolling(window=20, min_periods=20).min()
    data["rolling_high_20"] = data["high"].rolling(window=20, min_periods=20).max()
    data["range_20d"] = data["rolling_high_20"] - data["rolling_low_20"]
    data["returns"] = data["close"].pct_change()
    data["volatility_20d"] = data["returns"].rolling(window=20, min_periods=20).std(ddof=0) * sqrt(
        20.0,
    )
    data["avg_amount_5d"] = data["amount"].rolling(window=5, min_periods=5).mean()
    data["avg_amount_20d"] = data["amount"].rolling(window=20, min_periods=20).mean()
    data["amount_ratio_5d_20d"] = _safe_ratio_series(
        data["avg_amount_5d"],
        data["avg_amount_20d"],
    )
    data["support_level_20d"] = data["rolling_low_20"]
    data["resistance_level_20d"] = data["rolling_high_20"]
    data["distance_to_support_pct"] = (
        (data["close"] - data["support_level_20d"])
        / data["support_level_20d"].replace(0.0, pd.NA)
        * 100.0
    )
    data["distance_to_resistance_pct"] = (
        (data["resistance_level_20d"] - data["close"])
        / data["close"].replace(0.0, pd.NA)
        * 100.0
    )
    return data


def _build_process_metrics(latest_map: dict[str, Optional[float]]) -> ScreenerProcessMetrics:
    return ScreenerProcessMetrics(
        ma_5=latest_map.get("ma5"),
        ma_10=latest_map.get("ma10"),
        ma_20=latest_map.get("ma20"),
        ma_60=latest_map.get("ma60"),
        ma_120=latest_map.get("ma120"),
        ma_20_slope=latest_map.get("ma20_slope"),
        ma_60_slope=latest_map.get("ma60_slope"),
        close_percentile_60d=latest_map.get("close_percentile_60d"),
        return_20d=latest_map.get("return_20d"),
        return_60d=latest_map.get("return_60d"),
        atr_20=latest_map.get("atr20"),
        atr_20_pct=latest_map.get("atr20_pct"),
        range_20d=latest_map.get("range_20d"),
        volatility_20d=latest_map.get("volatility_20d"),
        avg_amount_5d=latest_map.get("avg_amount_5d"),
        avg_amount_20d=latest_map.get("avg_amount_20d"),
        amount_ratio_5d_20d=latest_map.get("amount_ratio_5d_20d"),
        support_level_20d=latest_map.get("support_level_20d"),
        resistance_level_20d=latest_map.get("resistance_level_20d"),
        distance_to_support_pct=latest_map.get("distance_to_support_pct"),
        distance_to_resistance_pct=latest_map.get("distance_to_resistance_pct"),
    )


def _build_atomic_factors(
    *,
    process_metrics: ScreenerProcessMetrics,
    raw_inputs: ScreenerRawInputs,
    as_of_date: date,
) -> ScreenerAtomicFactors:
    latest_close = raw_inputs.latest_close
    enough_bars = (raw_inputs.bars_count or 0) >= 60
    is_new_listing_risk = None
    if raw_inputs.list_date is not None:
        is_new_listing_risk = (as_of_date - raw_inputs.list_date).days < 180

    close_above_ma20 = _compare_gt(latest_close, process_metrics.ma_20)
    close_above_ma60 = _compare_gt(latest_close, process_metrics.ma_60)
    ma20_above_ma60 = _compare_gt(process_metrics.ma_20, process_metrics.ma_60)
    ma20_slope_positive = _compare_gte(process_metrics.ma_20_slope, 0.0)
    ma60_slope_positive = _compare_gte(process_metrics.ma_60_slope, 0.0)

    return ScreenerAtomicFactors(
        basic_universe_eligibility=(
            enough_bars
            and not bool(raw_inputs.is_st)
            and not bool(raw_inputs.is_suspended)
            and not bool(is_new_listing_risk)
        ),
        close_above_ma20=close_above_ma20,
        close_above_ma60=close_above_ma60,
        ma20_above_ma60=ma20_above_ma60,
        ma20_slope_positive=ma20_slope_positive,
        ma60_slope_positive=ma60_slope_positive,
        trend_state_basic=_infer_trend_state_basic(
            close_above_ma20=close_above_ma20,
            close_above_ma60=close_above_ma60,
            ma20_above_ma60=ma20_above_ma60,
            ma20_slope_positive=ma20_slope_positive,
            ma60_slope_positive=ma60_slope_positive,
        ),
        return_20d_strength=process_metrics.return_20d,
        return_60d_strength=process_metrics.return_60d,
        close_percentile_strength=process_metrics.close_percentile_60d,
        atr_pct_state=_classify_atr_pct_state(process_metrics.atr_20_pct),
        range_state=_classify_range_state(
            range_20d=process_metrics.range_20d,
            latest_close=latest_close,
        ),
        near_support=_classify_near_support(process_metrics.distance_to_support_pct),
        breakout_ready=_classify_breakout_ready(
            process_metrics.distance_to_resistance_pct,
            process_metrics.return_20d,
        ),
        distance_to_resistance_state=_classify_distance_state(
            process_metrics.distance_to_resistance_pct,
            near_threshold=2.5,
            far_threshold=8.0,
        ),
        amount_level_state=_classify_liquidity_state(process_metrics.avg_amount_20d),
        amount_ratio_state=_classify_liquidity_ratio_state(process_metrics.amount_ratio_5d_20d),
        liquidity_pass=_compare_gte(process_metrics.avg_amount_20d, 20_000_000.0),
        is_new_listing_risk=is_new_listing_risk,
        is_st_risk=raw_inputs.is_st,
        is_suspended_risk=raw_inputs.is_suspended,
    )


def _infer_trend_state_basic(
    *,
    close_above_ma20: Optional[bool],
    close_above_ma60: Optional[bool],
    ma20_above_ma60: Optional[bool],
    ma20_slope_positive: Optional[bool],
    ma60_slope_positive: Optional[bool],
) -> Optional[str]:
    if all(
        value is True
        for value in (
            close_above_ma20,
            close_above_ma60,
            ma20_above_ma60,
            ma20_slope_positive,
            ma60_slope_positive,
        )
    ):
        return "up"

    if all(
        value is False
        for value in (
            close_above_ma20,
            close_above_ma60,
            ma20_above_ma60,
        )
    ) and any(value is False for value in (ma20_slope_positive, ma60_slope_positive)):
        return "down"

    return "neutral"


def _classify_atr_pct_state(value: Optional[float]) -> Optional[AtrPctState]:
    if value is None:
        return "unknown"
    if value <= 0.02:
        return "low"
    if value >= 0.05:
        return "high"
    return "normal"


def _classify_range_state(
    *,
    range_20d: Optional[float],
    latest_close: Optional[float],
) -> Optional[RangeState]:
    if range_20d is None or latest_close is None or latest_close <= 0:
        return "unknown"
    ratio = range_20d / latest_close
    if ratio <= 0.12:
        return "compressed"
    if ratio >= 0.30:
        return "expanded"
    return "normal"


def _classify_near_support(distance_to_support_pct: Optional[float]) -> Optional[bool]:
    if distance_to_support_pct is None:
        return None
    return 0.0 <= distance_to_support_pct <= 4.0


def _classify_breakout_ready(
    distance_to_resistance_pct: Optional[float],
    return_20d: Optional[float],
) -> Optional[bool]:
    if distance_to_resistance_pct is None:
        return None
    if not (0.0 <= distance_to_resistance_pct <= 2.5):
        return False
    if return_20d is None:
        return True
    return return_20d >= 0.0


def _classify_distance_state(
    value: Optional[float],
    *,
    near_threshold: float,
    far_threshold: float,
) -> Optional[DistanceState]:
    if value is None:
        return "unknown"
    if value <= near_threshold:
        return "near"
    if value >= far_threshold:
        return "far"
    return "mid"


def _classify_liquidity_state(value: Optional[float]) -> Optional[LiquidityState]:
    if value is None:
        return "unknown"
    if value < 20_000_000.0:
        return "low"
    if value >= 100_000_000.0:
        return "high"
    return "normal"


def _classify_liquidity_ratio_state(value: Optional[float]) -> Optional[LiquidityRatioState]:
    if value is None:
        return "unknown"
    if value < 0.8:
        return "contracting"
    if value >= 1.2:
        return "expanding"
    return "normal"


def _compare_gt(left: Optional[float], right: Optional[float]) -> Optional[bool]:
    if left is None or right is None:
        return None
    return left > right


def _compare_gte(left: Optional[float], right: float) -> Optional[bool]:
    if left is None:
        return None
    return left >= right


def _safe_ratio_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0.0, pd.NA)


def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
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
