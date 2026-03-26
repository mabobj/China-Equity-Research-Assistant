"""构建技术画像。"""

from __future__ import annotations

from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import TechnicalView
from app.schemas.technical import TechnicalSnapshot


def build_technical_view(
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> TechnicalView:
    """基于日线与盘中触发快照构建技术画像。"""
    key_levels: list[str] = [
        "最新收盘价 {price:.2f}".format(price=technical_snapshot.latest_close)
    ]
    if technical_snapshot.support_level is not None:
        key_levels.append(
            "支撑位 {price:.2f}".format(price=technical_snapshot.support_level)
        )
    if technical_snapshot.resistance_level is not None:
        key_levels.append(
            "压力位 {price:.2f}".format(price=technical_snapshot.resistance_level)
        )

    return TechnicalView(
        trend_state=technical_snapshot.trend_state,
        trigger_state=trigger_snapshot.trigger_state,
        latest_close=technical_snapshot.latest_close,
        support_level=technical_snapshot.support_level,
        resistance_level=technical_snapshot.resistance_level,
        key_levels=key_levels,
        tactical_read=_build_tactical_read(
            technical_snapshot=technical_snapshot,
            trigger_snapshot=trigger_snapshot,
        ),
        invalidation_hint=_build_invalidation_hint(
            technical_snapshot=technical_snapshot,
            trigger_snapshot=trigger_snapshot,
        ),
    )


def _build_tactical_read(
    *,
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> str:
    if trigger_snapshot.trigger_state == "near_support":
        return "价格靠近日线支撑区，若回踩后企稳，更适合按回踩确认思路观察。"
    if trigger_snapshot.trigger_state == "near_breakout":
        return "价格靠近日线压力区，上行趋势下更适合观察是否出现有效突破。"
    if trigger_snapshot.trigger_state == "overstretched":
        return "价格已经偏离关键位，短线追价性价比一般，先避免在拉伸段激进入场。"
    if trigger_snapshot.trigger_state == "invalid":
        return "盘中触发条件暂不可用，当前更适合回到日线结构做保守判断。"
    if technical_snapshot.trend_state == "up":
        return "日线趋势仍偏强，但盘中尚未给出明确回踩或突破触发，适合继续等待更清晰位置。"
    if technical_snapshot.trend_state == "down":
        return "日线趋势偏弱，盘中即便有反弹，也更像观察信号而非直接执行信号。"
    return "日线趋势中性，盘中位置尚处于区间内部，战术上以等待更清晰方向为主。"


def _build_invalidation_hint(
    *,
    technical_snapshot: TechnicalSnapshot,
    trigger_snapshot: TriggerSnapshot,
) -> str:
    if technical_snapshot.support_level is not None:
        return "若后续价格持续跌破 {price:.2f} 附近支撑，当前技术判断需要下修。".format(
            price=technical_snapshot.support_level
        )
    if trigger_snapshot.trigger_state == "overstretched":
        return "若盘中拉伸后无法守住强势位置，当前技术优势会快速衰减。"
    return "若趋势状态由非下行转为下行，当前技术观察结论需要重新评估。"
