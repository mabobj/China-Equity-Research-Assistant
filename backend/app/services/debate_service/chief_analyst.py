"""首席分析员。"""

from __future__ import annotations

from app.schemas.debate import BearCase, BullCase, ChiefJudgement
from app.schemas.review import FactorProfileView, StrategySummary


def build_chief_judgement(
    *,
    bull_case: BullCase,
    bear_case: BearCase,
    factor_profile: FactorProfileView,
    strategy_summary: StrategySummary,
) -> ChiefJudgement:
    """整合多空分歧与策略约束，输出首席裁决。"""
    key_disagreements = _build_key_disagreements(
        bull_case=bull_case,
        bear_case=bear_case,
        factor_profile=factor_profile,
        strategy_summary=strategy_summary,
    )
    decisive_points = _build_decisive_points(
        factor_profile=factor_profile,
        strategy_summary=strategy_summary,
        bull_case=bull_case,
        bear_case=bear_case,
    )

    return ChiefJudgement(
        final_action=strategy_summary.action,
        summary=_build_summary(strategy_summary.action, key_disagreements),
        decisive_points=decisive_points,
        key_disagreements=key_disagreements,
    )


def _build_key_disagreements(
    *,
    bull_case: BullCase,
    bear_case: BearCase,
    factor_profile: FactorProfileView,
    strategy_summary: StrategySummary,
) -> list[str]:
    disagreements: list[str] = []
    if factor_profile.alpha_score >= 65 and factor_profile.risk_score >= 60:
        disagreements.append("中期 alpha 优势与短线风险约束同时存在。")
    if strategy_summary.action == "WATCH":
        disagreements.append("当前更像观察窗口，而不是直接执行窗口。")
    if bull_case.reasons and bear_case.reasons:
        disagreements.append("多头强调趋势与催化，空头强调位置与纪律。")
    if not disagreements:
        disagreements.append("当前分歧更多集中在执行时点，而不是方向本身。")
    return disagreements[:3]


def _build_decisive_points(
    *,
    factor_profile: FactorProfileView,
    strategy_summary: StrategySummary,
    bull_case: BullCase,
    bear_case: BearCase,
) -> list[str]:
    points = [
        "alpha 分 {score}".format(score=factor_profile.alpha_score),
        "风险分 {score}".format(score=factor_profile.risk_score),
        "策略类型 {strategy_type}".format(strategy_type=strategy_summary.strategy_type),
    ]
    if bull_case.reasons:
        points.append("多头首要理由: {title}".format(title=bull_case.reasons[0].title))
    if bear_case.reasons:
        points.append("空头首要理由: {title}".format(title=bear_case.reasons[0].title))
    return points[:3]


def _build_summary(action: str, key_disagreements: list[str]) -> str:
    if action == "BUY":
        return "首席分析员认为当前可以执行，但必须在既定触发与风控边界内推进。"
    if action == "WATCH":
        return "首席分析员认为当前仍以观察为主，核心分歧是时点而不是方向。"
    if key_disagreements:
        return "首席分析员认为当前回避更稳妥，主要原因在于优势尚未压过风险约束。"
    return "首席分析员认为当前不适合主动交易。"
