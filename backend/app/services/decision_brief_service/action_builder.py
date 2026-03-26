"""Decision brief 行动层构建逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.debate import DebateReviewReport
from app.schemas.decision_brief import DecisionBriefAction, DecisionConvictionLevel
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan


@dataclass(frozen=True)
class ActionBuildResult:
    """行动层输出。"""

    action_now: DecisionBriefAction
    headline_verdict: str
    conviction_level: DecisionConvictionLevel
    what_to_do_next: list[str]
    next_review_window: str


def build_action_layer(
    *,
    name: str,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> ActionBuildResult:
    """把下层结果翻译成更直接的行动层输出。"""
    action_now = _resolve_action_now(
        review_report=review_report,
        debate_review=debate_review,
        strategy_plan=strategy_plan,
        trigger_snapshot=trigger_snapshot,
    )
    conviction_level = _resolve_conviction_level(
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        strategy_plan=strategy_plan,
    )
    return ActionBuildResult(
        action_now=action_now,
        headline_verdict=_build_headline_verdict(name=name, action_now=action_now),
        conviction_level=conviction_level,
        what_to_do_next=_build_next_actions(
            action_now=action_now,
            strategy_plan=strategy_plan,
            trigger_snapshot=trigger_snapshot,
        ),
        next_review_window=strategy_plan.review_timeframe,
    )


def _resolve_action_now(
    *,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> DecisionBriefAction:
    if (
        strategy_plan.action == "AVOID"
        or review_report.final_judgement.action == "AVOID"
        or debate_review.final_action == "AVOID"
    ):
        return "AVOID"

    if strategy_plan.action == "BUY":
        if (
            strategy_plan.strategy_type == "pullback"
            and trigger_snapshot.trigger_state == "near_support"
        ):
            return "BUY_NOW"
        if (
            strategy_plan.strategy_type == "breakout"
            and trigger_snapshot.trigger_state == "near_breakout"
        ):
            return "BUY_NOW"
        if strategy_plan.strategy_type == "pullback":
            return "WAIT_PULLBACK"
        if strategy_plan.strategy_type == "breakout":
            return "WAIT_BREAKOUT"
        return "BUY_NOW"

    if strategy_plan.strategy_type == "pullback":
        return "WAIT_PULLBACK"
    if strategy_plan.strategy_type == "breakout":
        return "WAIT_BREAKOUT"
    if trigger_snapshot.trigger_state == "near_support":
        return "WAIT_PULLBACK"
    if trigger_snapshot.trigger_state == "near_breakout":
        return "WAIT_BREAKOUT"
    return "RESEARCH_ONLY"


def _resolve_conviction_level(
    *,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
) -> DecisionConvictionLevel:
    conviction_score = round(
        (
            float(review_report.confidence)
            + float(debate_review.confidence)
            + float(strategy_plan.confidence)
            + float(factor_snapshot.alpha_score.total_score)
            + float(100 - factor_snapshot.risk_score.total_score)
        )
        / 5
    )
    if conviction_score >= 75:
        return "high"
    if conviction_score >= 55:
        return "medium"
    return "low"


def _build_headline_verdict(
    *,
    name: str,
    action_now: DecisionBriefAction,
) -> str:
    if action_now == "BUY_NOW":
        return f"{name} 已接近计划买点，但仍应小仓执行。"
    if action_now == "WAIT_PULLBACK":
        return f"{name} 还没到舒服买点，先等回踩确认。"
    if action_now == "WAIT_BREAKOUT":
        return f"{name} 先等突破确认，不要提前追价。"
    if action_now == "RESEARCH_ONLY":
        return f"{name} 目前更适合继续研究，先不急着下单。"
    return f"{name} 当前不在合适交易窗口，先回避。"


def _build_next_actions(
    *,
    action_now: DecisionBriefAction,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> list[str]:
    support_text = _format_price(trigger_snapshot.daily_support_level)
    resistance_text = _format_price(trigger_snapshot.daily_resistance_level)
    entry_range_text = _format_price_range(strategy_plan.ideal_entry_range)
    stop_loss_text = _format_price(strategy_plan.stop_loss_price)
    take_profit_text = _format_price_range(strategy_plan.take_profit_range)

    if action_now == "BUY_NOW":
        actions = [
            "按计划只做小仓试错，不在单日拉升时追高。",
            f"若日线收盘跌破 {stop_loss_text}，按纪律退出。",
        ]
        if take_profit_text != "-":
            actions.append(f"若价格进入 {take_profit_text} 区间，可考虑分批止盈。")
        return actions[:3]

    if action_now == "WAIT_PULLBACK":
        actions = [
            f"先等价格回到 {entry_range_text} 附近再复核，不在当前位置追单。",
            f"若先跌破 {support_text} 一带支撑，则取消这轮观察计划。",
        ]
        return actions[:3]

    if action_now == "WAIT_BREAKOUT":
        actions = [
            f"先等价格有效突破 {resistance_text} 后再复核，不提前埋伏。",
            "只有突破后仍能站稳，才考虑升级为交易计划。",
        ]
        return actions[:3]

    if action_now == "RESEARCH_ONLY":
        return [
            "先继续跟踪日线收盘、公告更新和情绪变化，不急着下单。",
            f"下一次复核前，重点看支撑 {support_text} 与压力 {resistance_text} 是否被有效突破。",
        ][:3]

    return [
        "当前先不建立新仓位，等待风险下降或触发条件改善后再看。",
        f"若后续重新回到 {entry_range_text} 或出现更强触发，再重新评估。",
    ][:3]


def _format_price(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _format_price_range(value: object) -> str:
    if value is None:
        return "-"
    low = getattr(value, "low", None)
    high = getattr(value, "high", None)
    if low is None or high is None:
        return "-"
    return f"{float(low):.2f} - {float(high):.2f}"
