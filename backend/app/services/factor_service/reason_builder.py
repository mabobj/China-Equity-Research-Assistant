"""基于因子贡献生成结构化推荐理由。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.factor import FactorSnapshot


@dataclass(frozen=True)
class FactorReasonSummary:
    """结构化理由摘要。"""

    top_positive_factors: list[str]
    top_negative_factors: list[str]
    short_reason: str
    risk_notes: list[str]


def build_reason_summary(
    factor_snapshot: FactorSnapshot,
    *,
    max_items: int = 3,
) -> FactorReasonSummary:
    """从因子快照生成推荐理由。"""
    positives: list[str] = []
    negatives: list[str] = []

    for group in factor_snapshot.factor_group_scores:
        positives.extend(group.top_positive_signals)
        negatives.extend(group.top_negative_signals)

    top_positive_factors = _dedupe_preserve_order(positives)[:max_items]
    top_negative_factors = _dedupe_preserve_order(negatives)[:max_items]

    short_parts: list[str] = []
    if top_positive_factors:
        short_parts.append("优势: " + "；".join(top_positive_factors[:2]))
    if top_negative_factors:
        short_parts.append("风险: " + "；".join(top_negative_factors[:2]))
    if not short_parts:
        short_parts.append("当前可用因子有限，先以基础趋势与风险约束观察。")

    risk_notes = list(top_negative_factors)
    if factor_snapshot.risk_score.total_score >= 70:
        risk_notes.append("综合风险分偏高，优先降低追价与重仓操作。")
    elif factor_snapshot.risk_score.total_score >= 55:
        risk_notes.append("综合风险分中等偏高，建议等待更清晰的触发条件。")

    return FactorReasonSummary(
        top_positive_factors=top_positive_factors,
        top_negative_factors=top_negative_factors,
        short_reason=" | ".join(short_parts),
        risk_notes=_dedupe_preserve_order(risk_notes)[:max_items],
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
