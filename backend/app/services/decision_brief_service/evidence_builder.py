"""Decision brief evidence layer and traceable evidence refs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.schemas.debate import DebateReviewReport
from app.schemas.decision_brief import DecisionBrief, DecisionBriefEvidence, DecisionPriceLevel
from app.schemas.evidence import EvidenceBundle, EvidenceManifest, EvidenceRef
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import StockReviewReport
from app.schemas.strategy import StrategyPlan


@dataclass(frozen=True)
class EvidenceBuildResult:
    """Evidence layer derived from existing structured outputs."""

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


def build_evidence_manifest(decision_brief: DecisionBrief) -> EvidenceManifest:
    """Flatten the evidence refs attached to a decision brief into top-level bundles."""

    bundles: list[EvidenceBundle] = []
    if decision_brief.key_evidence:
        bundles.append(
            EvidenceBundle(
                bundle_name="key_evidence",
                used_by="decision_brief",
                refs=[
                    ref
                    for item in decision_brief.key_evidence
                    for ref in item.evidence_refs
                ],
            )
        )
    if decision_brief.key_risks:
        bundles.append(
            EvidenceBundle(
                bundle_name="key_risks",
                used_by="decision_brief",
                refs=[
                    ref
                    for item in decision_brief.key_risks
                    for ref in item.evidence_refs
                ],
            )
        )
    if decision_brief.evidence_manifest_refs:
        bundles.append(
            EvidenceBundle(
                bundle_name="decision_brief",
                used_by="decision_brief",
                refs=decision_brief.evidence_manifest_refs,
            )
        )
    return EvidenceManifest(
        symbol=decision_brief.symbol,
        as_of_date=decision_brief.as_of_date,
        bundles=bundles,
    )


def _build_positive_evidence(
    *,
    factor_snapshot: FactorSnapshot,
    review_report: StockReviewReport,
    debate_review: DebateReviewReport,
    trigger_snapshot: TriggerSnapshot,
) -> list[DecisionBriefEvidence]:
    symbol = review_report.symbol
    as_of_date = review_report.as_of_date
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
            else f"{group.group_name} factor group is currently supportive."
        )
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=f"{group.group_name} factor support",
                detail=detail,
                source_module="factor_snapshot",
                evidence_refs=[
                    _factor_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path=f"factor_group_scores.{group.group_name}.score",
                        raw_value=group.score,
                        derived_value=detail,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    if trigger_snapshot.trigger_state in {"near_support", "near_breakout"}:
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Trigger position is actionable",
                detail=trigger_snapshot.trigger_note,
                source_module="trigger_snapshot",
                evidence_refs=[
                    _daily_bars_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="trigger_snapshot.trigger_state",
                        raw_value=trigger_snapshot.trigger_state,
                        derived_value=trigger_snapshot.trigger_note,
                        used_by="decision_brief",
                        note="Derived from daily support/resistance levels.",
                    )
                ],
            ),
        )

    if review_report.event_view.recent_catalysts:
        catalyst = review_report.event_view.recent_catalysts[0]
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Recent catalyst exists",
                detail=catalyst,
                source_module="review_report",
                evidence_refs=[
                    _review_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="event_view.recent_catalysts[0]",
                        raw_value=catalyst,
                        derived_value=catalyst,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    if review_report.fundamental_view.key_financial_flags:
        flag = review_report.fundamental_view.key_financial_flags[0]
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="No obvious financial red flag",
                detail=flag,
                source_module="review_report",
                evidence_refs=[
                    _review_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="fundamental_view.key_financial_flags[0]",
                        raw_value=flag,
                        derived_value=flag,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    for index, point in enumerate(debate_review.bull_case.reasons):
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=point.title,
                detail=point.detail,
                source_module="debate_review",
                evidence_refs=[
                    _debate_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path=f"bull_case.reasons[{index}]",
                        raw_value=point.detail,
                        derived_value=point.detail,
                        used_by="decision_brief",
                        provider=debate_review.runtime_mode,
                    )
                ],
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
    symbol = review_report.symbol
    as_of_date = review_report.as_of_date
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
            else f"{group.group_name} factor group is currently weak."
        )
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=f"{group.group_name} factor risk",
                detail=detail,
                source_module="factor_snapshot",
                evidence_refs=[
                    _factor_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path=f"factor_group_scores.{group.group_name}.score",
                        raw_value=group.score,
                        derived_value=detail,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    _append_unique(
        items,
        DecisionBriefEvidence(
            title="Technical invalidation",
            detail=review_report.technical_view.invalidation_hint,
            source_module="review_report",
            evidence_refs=[
                _review_ref(
                    symbol=symbol,
                    as_of_date=as_of_date,
                    field_path="technical_view.invalidation_hint",
                    raw_value=review_report.technical_view.invalidation_hint,
                    derived_value=review_report.technical_view.invalidation_hint,
                    used_by="decision_brief",
                )
            ],
        ),
    )

    if review_report.fundamental_view.data_completeness_note:
        note = review_report.fundamental_view.data_completeness_note
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Fundamental confidence is constrained",
                detail=note,
                source_module="review_report",
                evidence_refs=[
                    _review_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="fundamental_view.data_completeness_note",
                        raw_value=note,
                        derived_value=note,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    if review_report.event_view.recent_risks:
        risk = review_report.event_view.recent_risks[0]
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Recent event risk",
                detail=risk,
                source_module="review_report",
                evidence_refs=[
                    _review_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="event_view.recent_risks[0]",
                        raw_value=risk,
                        derived_value=risk,
                        used_by="decision_brief",
                    )
                ],
            ),
        )

    for index, point in enumerate(debate_review.bear_case.reasons):
        _append_unique(
            items,
            DecisionBriefEvidence(
                title=point.title,
                detail=point.detail,
                source_module="debate_review",
                evidence_refs=[
                    _debate_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path=f"bear_case.reasons[{index}]",
                        raw_value=point.detail,
                        derived_value=point.detail,
                        used_by="decision_brief",
                        provider=debate_review.runtime_mode,
                    )
                ],
            ),
        )
        if len(items) >= 5:
            break

    if len(items) < 5 and debate_review.risk_review.execution_reminders:
        reminder = debate_review.risk_review.execution_reminders[0]
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Execution reminder",
                detail=reminder,
                source_module="debate_review",
                evidence_refs=[
                    _debate_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="risk_review.execution_reminders[0]",
                        raw_value=reminder,
                        derived_value=reminder,
                        used_by="decision_brief",
                        provider=debate_review.runtime_mode,
                    )
                ],
            ),
        )

    if len(items) < 5 and trigger_snapshot.trigger_state == "invalid":
        _append_unique(
            items,
            DecisionBriefEvidence(
                title="Trigger has turned invalid",
                detail=trigger_snapshot.trigger_note,
                source_module="trigger_snapshot",
                evidence_refs=[
                    _daily_bars_ref(
                        symbol=symbol,
                        as_of_date=as_of_date,
                        field_path="trigger_snapshot.trigger_state",
                        raw_value=trigger_snapshot.trigger_state,
                        derived_value=trigger_snapshot.trigger_note,
                        used_by="decision_brief",
                        note="Derived from daily support/resistance levels.",
                    )
                ],
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
                label="Ideal entry zone",
                value_text=(
                    f"{strategy_plan.ideal_entry_range.low:.2f} - "
                    f"{strategy_plan.ideal_entry_range.high:.2f}"
                ),
                note="Wait for price to move back into this zone before re-checking.",
            )
        )

    if trigger_snapshot.daily_support_level is not None:
        levels.append(
            DecisionPriceLevel(
                label="Daily support",
                value_text=f"{trigger_snapshot.daily_support_level:.2f}",
                note="Reassess the thesis if this level breaks on a closing basis.",
            )
        )

    if trigger_snapshot.daily_resistance_level is not None:
        levels.append(
            DecisionPriceLevel(
                label="Daily resistance",
                value_text=f"{trigger_snapshot.daily_resistance_level:.2f}",
                note="A clean break above this level would improve execution quality.",
            )
        )

    if strategy_plan.stop_loss_price is not None:
        levels.append(
            DecisionPriceLevel(
                label="Stop-loss reference",
                value_text=f"{strategy_plan.stop_loss_price:.2f}",
                note="Respect this level before discussing averaging down.",
            )
        )

    if strategy_plan.take_profit_range is not None:
        levels.append(
            DecisionPriceLevel(
                label="Target zone",
                value_text=(
                    f"{strategy_plan.take_profit_range.low:.2f} - "
                    f"{strategy_plan.take_profit_range.high:.2f}"
                ),
                note="Consider phased profit taking once price reaches this zone.",
            )
        )

    return levels


def _factor_ref(
    *,
    symbol: str,
    as_of_date: date,
    field_path: str,
    raw_value,
    derived_value,
    used_by,
) -> EvidenceRef:
    return EvidenceRef(
        dataset="factor_snapshot_daily",
        provider="computed",
        symbol=symbol,
        as_of_date=as_of_date,
        field_path=field_path,
        raw_value=raw_value,
        derived_value=derived_value,
        used_by=used_by,
        note="Derived from the daily factor snapshot.",
    )


def _review_ref(
    *,
    symbol: str,
    as_of_date: date,
    field_path: str,
    raw_value,
    derived_value,
    used_by,
) -> EvidenceRef:
    return EvidenceRef(
        dataset="review_report_daily",
        provider="computed",
        symbol=symbol,
        as_of_date=as_of_date,
        field_path=field_path,
        raw_value=raw_value,
        derived_value=derived_value,
        used_by=used_by,
        note="Derived from the structured review report.",
    )


def _debate_ref(
    *,
    symbol: str,
    as_of_date: date,
    field_path: str,
    raw_value,
    derived_value,
    used_by,
    provider: str,
) -> EvidenceRef:
    return EvidenceRef(
        dataset="debate_review_daily",
        provider=provider,
        symbol=symbol,
        as_of_date=as_of_date,
        field_path=field_path,
        raw_value=raw_value,
        derived_value=derived_value,
        used_by=used_by,
        note="Derived from the structured debate review.",
    )


def _daily_bars_ref(
    *,
    symbol: str,
    as_of_date: date,
    field_path: str,
    raw_value,
    derived_value,
    used_by,
    note: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        dataset="daily_bars_daily",
        provider="local_first",
        symbol=symbol,
        as_of_date=as_of_date,
        field_path=field_path,
        raw_value=raw_value,
        derived_value=derived_value,
        used_by=used_by,
        note=note,
    )


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
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(item.strip())
        if len(results) >= 3:
            break
    return results


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())
