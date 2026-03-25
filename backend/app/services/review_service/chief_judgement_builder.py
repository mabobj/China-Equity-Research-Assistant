"""构建首席裁决与策略摘要。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.review import (
    BullBearCase,
    EventView,
    FactorProfileView,
    FinalJudgement,
    SentimentView,
    StrategySummary,
    TechnicalView,
)
from app.schemas.strategy import StrategyPlan


@dataclass(frozen=True)
class ChiefJudgementBuildResult:
    """首席裁决构建结果。"""

    final_judgement: FinalJudgement
    strategy_summary: StrategySummary
    confidence: int


def build_chief_judgement(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    bull_case: BullBearCase,
    bear_case: BullBearCase,
    key_disagreements: list[str],
    strategy_plan: StrategyPlan,
) -> ChiefJudgementBuildResult:
    """生成最终裁决和策略摘要。"""
    strategy_summary = _build_strategy_summary(strategy_plan)
    confidence = _build_confidence(
        factor_profile=factor_profile,
        strategy_plan=strategy_plan,
    )

    return ChiefJudgementBuildResult(
        final_judgement=FinalJudgement(
            action=strategy_plan.action,
            summary=_build_final_summary(
                action=strategy_plan.action,
                factor_profile=factor_profile,
                technical_view=technical_view,
                event_view=event_view,
                sentiment_view=sentiment_view,
                bull_case=bull_case,
                bear_case=bear_case,
            ),
            key_points=_build_key_points(
                strategy_plan=strategy_plan,
                key_disagreements=key_disagreements,
            ),
        ),
        strategy_summary=strategy_summary,
        confidence=confidence,
    )


def _build_strategy_summary(strategy_plan: StrategyPlan) -> StrategySummary:
    if strategy_plan.action == "BUY":
        summary = "策略层允许执行，优先按 {strategy_type} 方案，在 {window} 内寻找合适触发。".format(
            strategy_type=strategy_plan.strategy_type,
            window=strategy_plan.entry_window,
        )
    elif strategy_plan.action == "WATCH":
        summary = "策略层仍以观察为主，等待更好的价格位置或更明确的突破条件。"
    else:
        summary = "策略层当前不建议主动建立新仓位，应先回避高不确定性阶段。"

    return StrategySummary(
        action=strategy_plan.action,
        strategy_type=strategy_plan.strategy_type,
        entry_window=strategy_plan.entry_window,
        ideal_entry_range=strategy_plan.ideal_entry_range,
        stop_loss_price=strategy_plan.stop_loss_price,
        take_profit_range=strategy_plan.take_profit_range,
        review_timeframe=strategy_plan.review_timeframe,
        concise_summary=summary,
    )


def _build_confidence(
    *,
    factor_profile: FactorProfileView,
    strategy_plan: StrategyPlan,
) -> int:
    score = round(
        factor_profile.alpha_score * 0.35
        + factor_profile.trigger_score * 0.2
        + (100 - factor_profile.risk_score) * 0.2
        + strategy_plan.confidence * 0.25
    )
    return max(0, min(100, score))


def _build_final_summary(
    *,
    action: str,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    bull_case: BullBearCase,
    bear_case: BullBearCase,
) -> str:
    if action == "BUY":
        return "综合因子、技术与策略层结论，当前允许继续关注并尝试执行，但前提是严格按触发与止损规则推进。"
    if action == "WATCH":
        return "当前更适合把这只股票放在重点观察名单中，等待技术位置或事件面进一步确认，再决定是否升级为执行计划。"
    if factor_profile.risk_score >= 60 or technical_view.trigger_state == "overstretched":
        return "当前风险与位置约束占上风，优先保持回避，避免在不利赔率阶段强行参与。"
    if event_view.recent_risks and sentiment_view.sentiment_bias == "bearish":
        return "事件扰动与情绪压力同时存在，当前裁决以保守回避为主。"
    if bull_case.reasons and bear_case.reasons:
        return "当前空头约束仍强于多头理由，先保持回避更稳妥。"
    return "当前多头论点不足以压过空头约束，先保持回避更稳妥。"


def _build_key_points(
    *,
    strategy_plan: StrategyPlan,
    key_disagreements: list[str],
) -> list[str]:
    points: list[str] = [strategy_plan.entry_window]
    if strategy_plan.stop_loss_price is not None:
        points.append("止损参考 {price:.2f}".format(price=strategy_plan.stop_loss_price))
    if key_disagreements:
        points.append(key_disagreements[0])
    return points[:3]
