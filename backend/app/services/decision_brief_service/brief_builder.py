"""Decision brief assembly logic."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.debate import DebateReviewReport
from app.schemas.decision_brief import DecisionBrief, DecisionSourceModule
from app.schemas.evidence import EvidenceRef
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import StockProfile
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan
from app.services.decision_brief_service.action_builder import build_action_layer
from app.services.decision_brief_service.evidence_builder import build_evidence_layer


def build_decision_brief(
    *,
    profile: StockProfile,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
    freshness_mode: str | None = None,
    source_mode: str | None = None,
    evidence_manifest_refs: list[EvidenceRef] | None = None,
) -> DecisionBrief:
    """Rebuild the top-level decision brief from existing module outputs."""

    action_layer = build_action_layer(
        name=profile.name,
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        strategy_plan=strategy_plan,
        trigger_snapshot=trigger_snapshot,
    )
    evidence_layer = build_evidence_layer(
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        strategy_plan=strategy_plan,
        trigger_snapshot=trigger_snapshot,
    )
    as_of_date = _resolve_as_of_date(
        review_report=review_report,
        strategy_plan=strategy_plan,
        factor_snapshot=factor_snapshot,
    )

    return DecisionBrief(
        symbol=profile.symbol,
        name=profile.name,
        as_of_date=as_of_date,
        freshness_mode=freshness_mode,
        source_mode=source_mode,
        headline_verdict=action_layer.headline_verdict,
        action_now=action_layer.action_now,
        conviction_level=action_layer.conviction_level,
        why_it_made_the_list=evidence_layer.why_it_made_the_list,
        why_not_all_in=evidence_layer.why_not_all_in,
        key_evidence=evidence_layer.key_evidence,
        key_risks=evidence_layer.key_risks,
        price_levels_to_watch=evidence_layer.price_levels_to_watch,
        what_to_do_next=action_layer.what_to_do_next,
        next_review_window=action_layer.next_review_window,
        source_modules=_build_source_modules(
            profile=profile,
            factor_snapshot=factor_snapshot,
            review_report=review_report,
            debate_review=debate_review,
            strategy_plan=strategy_plan,
            trigger_snapshot=trigger_snapshot,
        ),
        evidence_manifest_refs=evidence_manifest_refs or _collect_brief_refs(evidence_layer),
    )


def _collect_brief_refs(evidence_layer) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for item in [*evidence_layer.key_evidence, *evidence_layer.key_risks]:
        refs.extend(item.evidence_refs)
    return refs


def _resolve_as_of_date(
    *,
    review_report: StockReviewReport,
    strategy_plan: StrategyPlan,
    factor_snapshot: FactorSnapshot,
) -> date:
    if review_report.as_of_date:
        return review_report.as_of_date
    if strategy_plan.as_of_date:
        return strategy_plan.as_of_date
    return factor_snapshot.as_of_date


def _build_source_modules(
    *,
    profile: StockProfile,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    strategy_plan: StrategyPlan,
    trigger_snapshot: TriggerSnapshot,
) -> list[DecisionSourceModule]:
    return [
        DecisionSourceModule(
            module_name="stock_profile",
            note=f"source={profile.source}",
        ),
        DecisionSourceModule(
            module_name="factor_snapshot",
            as_of=_format_time(factor_snapshot.as_of_date),
            note=(
                f"alpha {factor_snapshot.alpha_score.total_score} / "
                f"trigger {factor_snapshot.trigger_score.total_score} / "
                f"risk {factor_snapshot.risk_score.total_score}"
            ),
        ),
        DecisionSourceModule(
            module_name="review_report",
            as_of=_format_time(review_report.as_of_date),
            note=f"final_action={review_report.final_judgement.action}",
        ),
        DecisionSourceModule(
            module_name="debate_review",
            as_of=_format_time(debate_review.as_of_date),
            note=f"runtime_mode={debate_review.runtime_mode}",
        ),
        DecisionSourceModule(
            module_name="strategy_plan",
            as_of=_format_time(strategy_plan.as_of_date),
            note=f"strategy_type={strategy_plan.strategy_type}",
        ),
        DecisionSourceModule(
            module_name="trigger_snapshot",
            as_of=_format_time(trigger_snapshot.as_of_datetime),
            note=f"trigger_state={trigger_snapshot.trigger_state}",
        ),
    ]


def _format_time(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value.isoformat()
