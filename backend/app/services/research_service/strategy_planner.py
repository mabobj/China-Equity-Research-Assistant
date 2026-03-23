"""结构化交易策略规划器。"""

from typing import Optional

from app.schemas.research import ResearchReport
from app.schemas.strategy import PriceRange, StrategyPlan
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.exceptions import DataServiceError, ProviderError
from app.services.data_service.market_data_service import MarketDataService
from app.services.feature_service.technical_analysis_service import TechnicalAnalysisService
from app.services.research_service.research_manager import ResearchManager


class StrategyPlanner:
    """基于研究报告与技术快照生成结构化策略计划。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        research_manager: ResearchManager,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._research_manager = research_manager

    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        """生成单票结构化交易策略计划。"""
        try:
            profile = self._market_data_service.get_stock_profile(symbol)
            technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
                symbol=symbol,
            )
            research_report = self._research_manager.get_research_report(symbol)
        except DataServiceError:
            raise
        except Exception as exc:
            raise ProviderError("Failed to build strategy inputs.") from exc

        strategy_type = _determine_strategy_type(
            action=research_report.action,
            snapshot=technical_snapshot,
        )
        entry_range = _build_entry_range(
            strategy_type=strategy_type,
            snapshot=technical_snapshot,
        )
        stop_loss_price = _build_stop_loss_price(
            strategy_type=strategy_type,
            snapshot=technical_snapshot,
        )
        take_profit_range = _build_take_profit_range(
            strategy_type=strategy_type,
            snapshot=technical_snapshot,
            entry_range=entry_range,
        )

        return StrategyPlan(
            symbol=research_report.symbol,
            name=profile.name,
            as_of_date=research_report.as_of_date,
            action=research_report.action,
            strategy_type=strategy_type,
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=entry_range,
            entry_triggers=_build_entry_triggers(
                strategy_type=strategy_type,
                snapshot=technical_snapshot,
                report=research_report,
            ),
            avoid_if=_build_avoid_conditions(
                strategy_type=strategy_type,
                snapshot=technical_snapshot,
                report=research_report,
            ),
            initial_position_hint=_build_initial_position_hint(
                action=research_report.action,
                confidence=research_report.confidence,
                snapshot=technical_snapshot,
            ),
            stop_loss_price=stop_loss_price,
            stop_loss_rule=_build_stop_loss_rule(
                strategy_type=strategy_type,
                stop_loss_price=stop_loss_price,
                snapshot=technical_snapshot,
            ),
            take_profit_range=take_profit_range,
            take_profit_rule=_build_take_profit_rule(
                strategy_type=strategy_type,
                take_profit_range=take_profit_range,
            ),
            hold_rule=_build_hold_rule(
                strategy_type=strategy_type,
                snapshot=technical_snapshot,
            ),
            sell_rule=_build_sell_rule(
                strategy_type=strategy_type,
                snapshot=technical_snapshot,
                stop_loss_price=stop_loss_price,
            ),
            review_timeframe="daily_close_review",
            confidence=_build_strategy_confidence(
                report=research_report,
                snapshot=technical_snapshot,
            ),
        )


def _determine_strategy_type(
    action: str,
    snapshot: TechnicalSnapshot,
) -> str:
    """根据研究动作与技术状态选择策略类型。"""
    if action == "AVOID":
        return "no_trade"
    if action == "WATCH":
        return "wait"

    if (
        snapshot.trend_state == "up"
        and snapshot.resistance_level is not None
        and snapshot.latest_close >= snapshot.resistance_level * 0.97
    ):
        return "breakout"
    return "pullback"


def _build_entry_range(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
) -> Optional[PriceRange]:
    """根据策略类型构建入场区间。"""
    atr = snapshot.atr14 or max(snapshot.latest_close * 0.03, 0.01)

    if strategy_type == "pullback":
        anchor = snapshot.support_level or snapshot.moving_averages.ma20 or snapshot.latest_close
        low = max(anchor - atr * 0.5, 0.01)
        high = min(anchor + atr * 0.5, snapshot.latest_close)
        return _build_price_range(low=low, high=high)

    if strategy_type == "breakout":
        anchor = snapshot.resistance_level or snapshot.latest_close
        low = max(anchor, snapshot.latest_close)
        high = anchor + atr
        return _build_price_range(low=low, high=high)

    return None


def _build_stop_loss_price(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
) -> Optional[float]:
    """构建初始止损价。"""
    atr = snapshot.atr14 or max(snapshot.latest_close * 0.03, 0.01)

    if strategy_type == "pullback":
        base = snapshot.support_level or snapshot.moving_averages.ma20 or snapshot.latest_close
        return _round_price(max(base - atr, 0.01))

    if strategy_type == "breakout":
        base = snapshot.resistance_level or snapshot.latest_close
        return _round_price(max(base - atr, 0.01))

    return None


def _build_take_profit_range(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
    entry_range: Optional[PriceRange],
) -> Optional[PriceRange]:
    """构建止盈区间。"""
    if strategy_type in {"wait", "no_trade"} or entry_range is None:
        return None

    atr = snapshot.atr14 or max(snapshot.latest_close * 0.03, 0.01)
    if strategy_type == "pullback":
        first_target = snapshot.resistance_level or (entry_range.high + atr * 2.0)
        second_target = first_target + atr
        return _build_price_range(low=first_target, high=second_target)

    first_target = entry_range.high + atr * 1.5
    second_target = entry_range.high + atr * 2.5
    return _build_price_range(low=first_target, high=second_target)


def _build_entry_triggers(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
    report: ResearchReport,
) -> list[str]:
    """构建入场触发条件。"""
    if strategy_type == "pullback":
        return [
            "价格回踩支撑区后企稳，且日线收盘未明显跌破支撑位。",
            "MACD 柱体未继续明显走弱，趋势状态保持非下行。",
            "研究报告维持 {action}，综合评分保持在当前水平附近。".format(
                action=report.action,
            ),
        ]
    if strategy_type == "breakout":
        target = snapshot.resistance_level or snapshot.latest_close
        return [
            "价格有效突破压力位 {price:.2f} 并保持日线收盘站稳。".format(
                price=target,
            ),
            "突破时成交量不低于近 5 日均量，避免无量突破。",
            "突破后 MACD 与趋势分数没有同步转弱。",
        ]
    if strategy_type == "wait":
        return [
            "先等待价格在支撑与压力之间给出更明确方向。",
            "若研究评分和技术趋势同步改善，再考虑升级到买入计划。",
        ]
    return [
        "当前不建议主动建立新仓位，优先等待风险下降。",
    ]


def _build_avoid_conditions(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
    report: ResearchReport,
) -> list[str]:
    """构建避免入场条件。"""
    conditions = [
        "若日线收盘跌破关键支撑位，不在当前窗口内尝试买入。",
        "若研究报告 action 下修为 AVOID，则取消本轮计划。",
    ]
    if snapshot.volatility_state == "high":
        conditions.append("若波动继续放大且未形成稳定收盘结构，避免追价。")
    if strategy_type == "breakout":
        conditions.append("若突破后回落至压力位下方，视为假突破，不追单。")
    if report.risk_score >= 60:
        conditions.append("若风险评分继续上升，优先保留观察而非开仓。")
    return conditions[:3]


def _build_initial_position_hint(
    action: str,
    confidence: int,
    snapshot: TechnicalSnapshot,
) -> Optional[str]:
    """生成初始仓位提示。"""
    if action != "BUY":
        return None
    if confidence >= 70 and snapshot.volatility_state != "high":
        return "medium"
    return "small"


def _build_stop_loss_rule(
    strategy_type: str,
    stop_loss_price: Optional[float],
    snapshot: TechnicalSnapshot,
) -> str:
    """生成止损规则。"""
    if strategy_type == "no_trade":
        return "当前不设置交易止损，因为本计划不建议入场。"
    if strategy_type == "wait":
        return "等待更明确入场信号，未触发前不预设执行止损。"
    if stop_loss_price is None:
        return "若关键支撑失守，应重新评估交易计划并停止尝试入场。"
    return (
        "若买入后日线收盘跌破 {price:.2f}，或跌破支撑位并未在次日修复，则执行止损。"
    ).format(price=stop_loss_price)


def _build_take_profit_rule(
    strategy_type: str,
    take_profit_range: Optional[PriceRange],
) -> str:
    """生成止盈规则。"""
    if strategy_type == "no_trade":
        return "当前不设置止盈，因为本计划不建议入场。"
    if strategy_type == "wait":
        return "等待入场信号出现后，再根据突破或回踩形态设置止盈。"
    if take_profit_range is None:
        return "若价格接近前高或关键压力位，可分批兑现收益。"
    return "价格进入 {low:.2f}-{high:.2f} 区间后，可考虑分批止盈，不追求一次性卖在最高点。".format(
        low=take_profit_range.low,
        high=take_profit_range.high,
    )


def _build_hold_rule(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
) -> str:
    """生成持有规则。"""
    if strategy_type == "no_trade":
        return "当前计划以空仓观察为主，不适用持有规则。"
    if strategy_type == "wait":
        return "若已持有，可在价格未跌破支撑且趋势未转弱的前提下继续观察。"
    return (
        "若已买入，只要价格维持在支撑位上方，且趋势状态未转为 down，"
        "可继续持有并按日线收盘复核。"
    )


def _build_sell_rule(
    strategy_type: str,
    snapshot: TechnicalSnapshot,
    stop_loss_price: Optional[float],
) -> str:
    """生成卖出规则。"""
    if strategy_type == "no_trade":
        return "当前以避免新交易为主，不主动制定买入后的卖出执行。"
    if strategy_type == "wait":
        return "若已持有且价格跌破支撑、趋势转弱或研究报告转为 AVOID，应优先减仓或退出。"

    price_text = (
        "{price:.2f}".format(price=stop_loss_price)
        if stop_loss_price is not None
        else "关键支撑"
    )
    return (
        "若价格跌破 {price}、MACD 动能明显转负，或高波动伴随趋势转弱，"
        "应优先卖出而不是继续摊低成本。"
    ).format(price=price_text)


def _build_strategy_confidence(
    report: ResearchReport,
    snapshot: TechnicalSnapshot,
) -> int:
    """根据研究结论和波动状态微调策略置信度。"""
    confidence = float(report.confidence)
    if snapshot.volatility_state == "high":
        confidence -= 8
    elif snapshot.volatility_state == "low":
        confidence += 3

    if report.action == "AVOID":
        confidence += 2
    if report.action == "WATCH":
        confidence -= 4

    return _clamp_score(confidence)


def _build_price_range(low: float, high: float) -> PriceRange:
    """构建规范化价格区间。"""
    normalized_low = min(low, high)
    normalized_high = max(low, high)
    return PriceRange(
        low=_round_price(normalized_low),
        high=_round_price(normalized_high),
    )


def _round_price(value: float) -> float:
    """统一价格精度。"""
    return round(float(value), 2)


def _clamp_score(score: float) -> int:
    """将分数限制在 0 到 100。"""
    return max(0, min(100, int(round(score))))
