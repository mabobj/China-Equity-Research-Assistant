"""构建因子画像。"""

from __future__ import annotations

from app.schemas.factor import FactorSnapshot
from app.schemas.review import FactorProfileView

GROUP_LABELS = {
    "trend": "趋势",
    "quality": "质量",
    "growth": "成长",
    "low_vol": "低波动",
    "event": "事件",
}


def build_factor_profile_view(factor_snapshot: FactorSnapshot) -> FactorProfileView:
    """基于因子快照生成因子画像。"""
    ranked_groups = [
        group for group in factor_snapshot.factor_group_scores if group.score is not None
    ]
    ranked_groups.sort(key=lambda item: item.score or 0.0, reverse=True)

    strongest = [_format_group_name(group.group_name) for group in ranked_groups[:2]]
    weakest = [
        _format_group_name(group.group_name)
        for group in sorted(ranked_groups, key=lambda item: item.score or 0.0)[:2]
    ]

    summary_parts = [
        "alpha 分 {score}".format(score=factor_snapshot.alpha_score.total_score),
        "触发分 {score}".format(score=factor_snapshot.trigger_score.total_score),
        "风险分 {score}".format(score=factor_snapshot.risk_score.total_score),
    ]
    if strongest:
        summary_parts.append("当前相对占优维度: {items}".format(items="、".join(strongest)))
    if weakest:
        summary_parts.append("偏弱维度: {items}".format(items="、".join(weakest)))

    return FactorProfileView(
        strongest_factor_groups=strongest,
        weakest_factor_groups=weakest,
        alpha_score=factor_snapshot.alpha_score.total_score,
        trigger_score=factor_snapshot.trigger_score.total_score,
        risk_score=factor_snapshot.risk_score.total_score,
        concise_summary="；".join(summary_parts),
    )


def _format_group_name(group_name: str) -> str:
    return GROUP_LABELS.get(group_name, group_name)
