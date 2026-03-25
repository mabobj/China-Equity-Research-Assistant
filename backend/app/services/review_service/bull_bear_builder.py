"""构建多空观点与核心分歧。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.review import (
    BullBearCase,
    EventView,
    FactorProfileView,
    FundamentalView,
    SentimentView,
    StrategySummary,
    TechnicalView,
)


@dataclass(frozen=True)
class BullBearBuildResult:
    """多空观点构建结果。"""

    bull_case: BullBearCase
    bear_case: BullBearCase
    key_disagreements: list[str]


def build_bull_bear_case(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    fundamental_view: FundamentalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    strategy_summary: StrategySummary,
) -> BullBearBuildResult:
    """生成多头观点、空头观点和核心分歧。"""
    bull_reasons = _build_bull_reasons(
        factor_profile=factor_profile,
        technical_view=technical_view,
        fundamental_view=fundamental_view,
        event_view=event_view,
        sentiment_view=sentiment_view,
        strategy_summary=strategy_summary,
    )
    bear_reasons = _build_bear_reasons(
        factor_profile=factor_profile,
        technical_view=technical_view,
        fundamental_view=fundamental_view,
        event_view=event_view,
        sentiment_view=sentiment_view,
        strategy_summary=strategy_summary,
    )
    key_disagreements = _build_key_disagreements(
        factor_profile=factor_profile,
        technical_view=technical_view,
        fundamental_view=fundamental_view,
        event_view=event_view,
        sentiment_view=sentiment_view,
        strategy_summary=strategy_summary,
    )

    return BullBearBuildResult(
        bull_case=BullBearCase(
            stance="bull",
            summary="若强调优势与触发条件，当前更值得关注的多头论点主要来自因子优势、技术位置和潜在催化。",
            reasons=bull_reasons[:3],
        ),
        bear_case=BullBearCase(
            stance="bear",
            summary="若强调风险与执行纪律，当前需要谨慎对待的点主要来自风险分、位置约束和基本面短板。",
            reasons=bear_reasons[:3],
        ),
        key_disagreements=key_disagreements[:3],
    )


def _build_bull_reasons(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    fundamental_view: FundamentalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    strategy_summary: StrategySummary,
) -> list[str]:
    reasons: list[str] = []
    if factor_profile.alpha_score >= 65 and factor_profile.strongest_factor_groups:
        reasons.append(
            "因子层面以 {items} 为主要优势，alpha 读数维持在较高区间。".format(
                items="、".join(factor_profile.strongest_factor_groups[:2])
            )
        )
    if technical_view.trigger_state in {"near_support", "near_breakout"}:
        reasons.append(technical_view.tactical_read)
    if fundamental_view.quality_read and "偏弱" not in fundamental_view.quality_read:
        reasons.append(fundamental_view.quality_read)
    if event_view.recent_catalysts:
        reasons.append("近期事件面存在正向线索，例如: {item}。".format(item=event_view.recent_catalysts[0]))
    if sentiment_view.sentiment_bias == "bullish":
        reasons.append(sentiment_view.momentum_context)
    if strategy_summary.action == "BUY":
        reasons.append("现有策略计划并未回避交易，执行框架已经具备。")
    return _dedupe_preserve_order(reasons)


def _build_bear_reasons(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    fundamental_view: FundamentalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    strategy_summary: StrategySummary,
) -> list[str]:
    reasons: list[str] = []
    if factor_profile.risk_score >= 60:
        reasons.append("风险分已经偏高，意味着波动、结构或事件扰动需要更严格的仓位纪律。")
    if technical_view.trigger_state in {"overstretched", "invalid"}:
        reasons.append(technical_view.tactical_read)
    if fundamental_view.key_financial_flags:
        reasons.append("基本面仍需留意: {items}。".format(items="、".join(fundamental_view.key_financial_flags[:2])))
    if event_view.recent_risks:
        reasons.append("近期公告存在扰动，例如: {item}。".format(item=event_view.recent_risks[0]))
    if sentiment_view.sentiment_bias in {"cautious", "bearish"}:
        reasons.append(sentiment_view.crowding_hint)
    if strategy_summary.action == "AVOID":
        reasons.append("现有策略层已经给出回避交易的结论。")
    return _dedupe_preserve_order(reasons)


def _build_key_disagreements(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    fundamental_view: FundamentalView,
    event_view: EventView,
    sentiment_view: SentimentView,
    strategy_summary: StrategySummary,
) -> list[str]:
    disagreements: list[str] = []
    if factor_profile.alpha_score >= 65 and factor_profile.risk_score >= 60:
        disagreements.append("中期 alpha 优势与短线风险约束同时存在，是否立即执行仍有分歧。")
    if technical_view.trend_state == "up" and technical_view.trigger_state == "neutral":
        disagreements.append("趋势偏强，但当前触发位置并不便宜，需要等待更优入场条件。")
    if (
        fundamental_view.quality_read is not None
        and "尚可" in fundamental_view.quality_read
        and event_view.recent_risks
    ):
        disagreements.append("基本面没有明显失真，但事件面仍有扰动，短期节奏判断容易分化。")
    if sentiment_view.sentiment_bias == "bullish" and technical_view.trigger_state == "overstretched":
        disagreements.append("情绪与动量偏强，但短线位置已经拉伸，追价与等待之间存在分歧。")
    if strategy_summary.action == "WATCH" and not disagreements:
        disagreements.append("当前更像研究与等待阶段，而不是直接执行阶段。")
    if not disagreements:
        disagreements.append("优势与风险都不算极端，分歧主要集中在执行时点而非方向判断。")
    return _dedupe_preserve_order(disagreements)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
