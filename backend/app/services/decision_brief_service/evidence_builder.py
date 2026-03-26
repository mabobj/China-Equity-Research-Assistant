"""Decision brief 证据层构建逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.debate import DebateReviewReport
from app.schemas.decision_brief import DecisionBriefEvidence, DecisionPriceLevel
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan


@dataclass(frozen=True)
class EvidenceBuildResult:
    """证据层输出。"""

    why_it_made_the_list: list[str]
    why_not_all_in: list[str]
    key_evidence: list[DecisionBriefEvidence]
    key_risks: list[DecisionBriefEvidence]
    price_levels_to_watch: list[DecisionPriceLevel]


def build_evidence_layer(
    *,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> EvidenceBuildResult:
    """从已有模块里提炼可追溯证据。"""
    key_evidence = _build_positive_evidence(
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        trigger_snapshot=trigger_snapshot,
    )
    key_risks = _build_risk_evidence(
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        trigger_snapshot=trigger_snapshot,
    )
    why_it_made_the_list = _limit_texts(
        review_report.bull_case.reasons or [item.detail for item in key_evidence]
    )
    why_not_all_in = _limit_texts(
        review_report.bear_case.reasons or [item.detail for item in key_risks]
    )
    return EvidenceBuildResult(
        why_it_made_the_list=why_it_made_the_list,
        why_not_all_in=why_not_all_in,
        key_evidence=key_evidence,
        key_risks=key_risks,
        price_levels_to_watch=_build_price_levels(
            strategy_plan=strategy_plan,
            trigger_snapshot=trigger_snapshot,
        ),
    )


def _build_positive_evidence(
    *,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    trigger_snapshot: TriggerSnapshot,
) -> list[DecisionBriefEvidence]:
    items: list[DecisionBriefEvidence] = []

    strongest_groups = sorted(
        (
            group
            for group in factor_snapshot.factor_group_scores
            if group.score is not None and group.score >= 60
        ),
        key=lambda item: float(item.score or 0),
        reverse=True,
    )
    for group in strongest_groups[:2]:
        detail = (
            group.top_positive_signals[0]
            if group.top_positive_signals
            else f"{group.group_name} 因子组当前相对占优。"
        )
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=f"{group.group_name} 因子偏强",
                detail=detail,
                source_module="factor_snapshot",
            ),
        )

    if trigger_snapshot.trigger_state in {"near_support", "near_breakout"}:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="触发位置接近计划观察点",
                detail=trigger_snapshot.trigger_note,
                source_module="trigger_snapshot",
            ),
        )

    if review_report.event_view.recent_catalysts:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="近期存在催化",
                detail=review_report.event_view.recent_catalysts[0],
                source_module="review_report",
            ),
        )

    if review_report.fundamental_view.key_financial_flags:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="财务红旗暂不突出",
                detail=review_report.fundamental_view.key_financial_flags[0],
                source_module="review_report",
            ),
        )

    for point in debate_review.bull_case.reasons:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=point.title,
                detail=point.detail,
                source_module="debate_review",
            ),
        )
        if len(items) >= 5:
            break

    return items[:5]


def _build_risk_evidence(
    *,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    trigger_snapshot: TriggerSnapshot,
) -> list[DecisionBriefEvidence]:
    items: list[DecisionBriefEvidence] = []

    weakest_groups = sorted(
        (
            group
            for group in factor_snapshot.factor_group_scores
            if group.score is not None and group.score <= 45
        ),
        key=lambda item: float(item.score or 0),
    )
    for group in weakest_groups[:2]:
        detail = (
            group.top_negative_signals[0]
            if group.top_negative_signals
            else f"{group.group_name} 因子组当前相对偏弱。"
        )
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=f"{group.group_name} 因子偏弱",
                detail=detail,
                source_module="factor_snapshot",
            ),
        )

    _append_unique(
        items,
        DecisionBriefEvidence(
            title="技术失效条件",
            detail=review_report.technical_view.invalidation_hint,
            source_module="review_report",
        ),
    )

    if review_report.fundamental_view.data_completeness_note:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="基本面结论存在置信度约束",
                detail=review_report.fundamental_view.data_completeness_note,
                source_module="review_report",
            ),
        )

    if review_report.event_view.recent_risks:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="近期事件风险",
                detail=review_report.event_view.recent_risks[0],
                source_module="review_report",
            ),
        )

    for point in debate_review.bear_case.reasons:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=point.title,
                detail=point.detail,
                source_module="debate_review",
            ),
        )
        if len(items) >= 5:
            break

    if len(items) < 5 and debate_review.risk_review.execution_reminders:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="执行层风控提醒",
                detail=debate_review.risk_review.execution_reminders[0],
                source_module="debate_review",
            ),
        )

    if len(items) < 5 and trigger_snapshot.trigger_state == "invalid":
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="触发位置失效",
                detail=trigger_snapshot.trigger_note,
                source_module="trigger_snapshot",
            ),
        )

    return items[:5]


def _build_price_levels(
    *,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> list[DecisionPriceLevel]:
    levels: list[DecisionPriceLevel] = []

    if strategy_plan.ideal_entry_range is not None:
        levels.append(
            DecisionPriceLevel(
                label="理想观察区间",
                value_text=(
                    f"{strategy_plan.ideal_entry_range.low:.2f} - "
                    f"{strategy_plan.ideal_entry_range.high:.2f}"
                ),
                note="更适合等待价格回到这个区间后再复核。",
            )
        )

    if trigger_snapshot.daily_support_level is not None:
        levels.append(
            DecisionPriceLevel(
                label="日线支撑位",
                value_text=f"{trigger_snapshot.daily_support_level:.2f}",
                note="跌破后需要重新评估原判断。",
            )
        )

    if trigger_snapshot.daily_resistance_level is not None:
        levels.append(
            DecisionPriceLevel(
                label="日线压力位",
                value_text=f"{trigger_snapshot.daily_resistance_level:.2f}",
                note="突破并站稳后，执行层信号会更明确。",
            )
        )

    if strategy_plan.stop_loss_price is not None:
        levels.append(
            DecisionPriceLevel(
                label="止损参考位",
                value_text=f"{strategy_plan.stop_loss_price:.2f}",
                note="触发后优先遵守纪律，而不是继续扛单。",
            )
        )

    if strategy_plan.take_profit_range is not None:
        levels.append(
            DecisionPriceLevel(
                label="目标区间",
                value_text=(
                    f"{strategy_plan.take_profit_range.low:.2f} - "
                    f"{strategy_plan.take_profit_range.high:.2f}"
                ),
                note="进入区间后可考虑分批兑现。",
            )
        )

    return levels


def _append_unique(
    items: list[DecisionBriefEvidence],
    candidate: DecisionBriefEvidence,
) -> None:
    normalized = _normalize_text(candidate.detail)
    if not normalized:
        return
    if any(_normalize_text(item.detail) == normalized for item in items):
        return
    items.append(candidate)


def _limit_texts(items: list[str]) -> list[str]:
    results: list[str] = []
    for item in items:
        normalized = _normalize_text(item)
        if not normalized:
            continue
        if normalized in {_normalize_text(existing) for existing in results}:
            continue
        results.append(item.strip())
        if len(results) >= 3:
            break
    return results


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())
