"""风险复核员。"""

from __future__ import annotations

from app.schemas.debate import RiskReview
from app.schemas.review import FactorProfileView, TechnicalView, StrategySummary


def build_risk_review(
    *,
    factor_profile: FactorProfileView,
    technical_view: TechnicalView,
    strategy_summary: StrategySummary,
) -> RiskReview:
    """基于风险分、失效条件与策略约束输出风险复核。"""
    reminders: list[str] = [technical_view.invalidation_hint]
    if strategy_summary.stop_loss_price is not None:
        reminders.append(
            "严格观察止损参考位 {price:.2f}。".format(
                price=strategy_summary.stop_loss_price
            )
        )
    if strategy_summary.take_profit_range is not None:
        reminders.append(
            "到达止盈区间后应分批处理，而不是一次性放大目标。"
        )

    risk_level = "medium"
    if factor_profile.risk_score >= 70 or technical_view.trigger_state == "overstretched":
        risk_level = "high"
    elif factor_profile.risk_score <= 40 and technical_view.trigger_state in {
        "near_support",
        "near_breakout",
        "neutral",
    }:
        risk_level = "low"

    return RiskReview(
        risk_level=risk_level,
        summary=_build_summary(risk_level, strategy_summary.action),
        execution_reminders=reminders[:3],
    )


def _build_summary(risk_level: str, action: str) -> str:
    if risk_level == "high":
        return "风险复核认为当前执行压力较大，若无更强证据，不宜放松纪律。"
    if action == "BUY":
        return "风险复核认为当前可以执行，但必须把仓位、止损和止盈纪律前置。"
    return "风险复核认为当前风险可控但并不低，执行上仍应偏保守。"
