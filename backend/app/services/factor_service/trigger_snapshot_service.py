"""轻量触发快照 service。"""

from __future__ import annotations

from datetime import datetime, time
import logging

from app.schemas.intraday import IntradaySnapshot, TriggerSnapshot
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.intraday_service import IntradayService
from app.services.feature_service.technical_analysis_service import (
    TechnicalAnalysisService,
)

logger = logging.getLogger(__name__)


class TriggerSnapshotService:
    """结合日线技术快照与盘中快照生成触发快照。"""

    def __init__(
        self,
        technical_analysis_service: TechnicalAnalysisService,
        intraday_service: IntradayService,
    ) -> None:
        self._technical_analysis_service = technical_analysis_service
        self._intraday_service = intraday_service

    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        logger.debug(
            "trigger_snapshot.start symbol=%s frequency=%s limit=%s",
            symbol,
            frequency,
            limit,
        )
        technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
            symbol=symbol,
        )
        intraday_snapshot = self._intraday_service.get_intraday_snapshot(
            symbol=symbol,
            frequency=frequency,
            limit=limit,
        )
        snapshot = self.build_trigger_snapshot(
            technical_snapshot=technical_snapshot,
            intraday_snapshot=intraday_snapshot,
        )
        logger.debug(
            "trigger_snapshot.done symbol=%s trigger_state=%s latest_price=%s",
            symbol,
            snapshot.trigger_state,
            snapshot.latest_intraday_price,
        )
        return snapshot

    def build_daily_fallback_trigger_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
    ) -> TriggerSnapshot:
        """在缺少盘中数据时，基于日线快照生成保守版触发快照。"""
        logger.debug(
            "trigger_snapshot.fallback_build symbol=%s as_of_date=%s",
            technical_snapshot.symbol,
            technical_snapshot.as_of_date,
        )
        latest_price = technical_snapshot.latest_close
        support_level = technical_snapshot.support_level
        resistance_level = technical_snapshot.resistance_level
        distance_to_support_pct = _distance_from_level(latest_price, support_level)
        distance_to_resistance_pct = _distance_to_level(latest_price, resistance_level)

        trigger_state = "neutral"
        trigger_note = "缺少盘中数据，当前基于日线结构做保守判断。"

        if latest_price <= 0:
            trigger_state = "invalid"
            trigger_note = "最新收盘价无效，无法生成触发判断。"
        elif support_level is None and resistance_level is None:
            trigger_state = "invalid"
            trigger_note = "日线支撑位和压力位均缺失，无法生成触发判断。"
        elif support_level is not None and latest_price < support_level * 0.985:
            trigger_state = "overstretched"
            trigger_note = "收盘价已明显跌破日线支撑位，短线位置偏弱。"
        elif resistance_level is not None and latest_price > resistance_level * 1.02:
            trigger_state = "overstretched"
            trigger_note = "收盘价明显高于日线压力位，短线存在拉伸风险。"
        elif (
            technical_snapshot.trend_state == "up"
            and distance_to_resistance_pct is not None
            and 0 <= distance_to_resistance_pct <= 1.0
        ):
            trigger_state = "near_breakout"
            trigger_note = "缺少盘中数据，但日线收盘价已靠近日线压力位，可视为突破观察区。"
        elif distance_to_support_pct is not None and 0 <= distance_to_support_pct <= 2.0:
            trigger_state = "near_support"
            trigger_note = "缺少盘中数据，但日线收盘价靠近日线支撑位，可视为回踩观察区。"

        return TriggerSnapshot(
            symbol=technical_snapshot.symbol,
            as_of_datetime=datetime.combine(
                technical_snapshot.as_of_date,
                time(15, 0, 0),
            ),
            daily_trend_state=technical_snapshot.trend_state,
            daily_support_level=support_level,
            daily_resistance_level=resistance_level,
            latest_intraday_price=latest_price,
            distance_to_support_pct=distance_to_support_pct,
            distance_to_resistance_pct=distance_to_resistance_pct,
            trigger_state=trigger_state,
            trigger_note=trigger_note,
        )

    def build_trigger_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
        intraday_snapshot: IntradaySnapshot,
    ) -> TriggerSnapshot:
        latest_price = intraday_snapshot.latest_price
        support_level = technical_snapshot.support_level
        resistance_level = technical_snapshot.resistance_level
        distance_to_support_pct = _distance_from_level(latest_price, support_level)
        distance_to_resistance_pct = _distance_to_level(latest_price, resistance_level)

        trigger_state = "neutral"
        trigger_note = "盘中价格位于日线关键位置之间，暂未形成明确触发。"

        if latest_price <= 0:
            trigger_state = "invalid"
            trigger_note = "最新盘中价格无效，无法判断触发状态。"
        elif support_level is None and resistance_level is None:
            trigger_state = "invalid"
            trigger_note = "日线支撑位和压力位均缺失，无法生成触发判断。"
        elif support_level is not None and latest_price < support_level * 0.985:
            trigger_state = "overstretched"
            trigger_note = "盘中价格已明显跌破日线支撑，短线位置偏弱。"
        elif resistance_level is not None and latest_price > resistance_level * 1.02:
            trigger_state = "overstretched"
            trigger_note = "盘中价格已明显高于日线压力位，短线存在拉伸风险。"
        elif (
            technical_snapshot.trend_state == "up"
            and distance_to_resistance_pct is not None
            and 0 <= distance_to_resistance_pct <= 1.0
        ):
            trigger_state = "near_breakout"
            trigger_note = "盘中价格接近日线压力位，上行趋势下处于突破观察区。"
        elif distance_to_support_pct is not None and 0 <= distance_to_support_pct <= 2.0:
            trigger_state = "near_support"
            trigger_note = "盘中价格接近日线支撑位，可作为回踩观察区。"

        return TriggerSnapshot(
            symbol=technical_snapshot.symbol,
            as_of_datetime=intraday_snapshot.latest_datetime,
            daily_trend_state=technical_snapshot.trend_state,
            daily_support_level=support_level,
            daily_resistance_level=resistance_level,
            latest_intraday_price=latest_price,
            distance_to_support_pct=distance_to_support_pct,
            distance_to_resistance_pct=distance_to_resistance_pct,
            trigger_state=trigger_state,
            trigger_note=trigger_note,
        )


def _distance_from_level(
    latest_price: float,
    level: float | None,
) -> float | None:
    if level is None or level <= 0:
        return None
    return float((latest_price - level) / level * 100)


def _distance_to_level(
    latest_price: float,
    level: float | None,
) -> float | None:
    if level is None or latest_price <= 0:
        return None
    return float((level - latest_price) / latest_price * 100)
