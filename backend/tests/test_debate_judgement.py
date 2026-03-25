"""首席裁决与风险复核测试。"""

from app.schemas.debate import BearCase, BullCase, DebatePoint
from app.schemas.review import FactorProfileView, StrategySummary, TechnicalView
from app.schemas.strategy import PriceRange
from app.services.debate_service.chief_analyst import build_chief_judgement
from app.services.debate_service.risk_reviewer import build_risk_review


def test_chief_analyst_aggregates_debate_points() -> None:
    judgement = build_chief_judgement(
        bull_case=BullCase(
            summary="多头看法",
            reasons=[DebatePoint(title="趋势", detail="趋势偏强")],
        ),
        bear_case=BearCase(
            summary="空头看法",
            reasons=[DebatePoint(title="位置", detail="接近压力位")],
        ),
        factor_profile=FactorProfileView(
            strongest_factor_groups=["趋势"],
            weakest_factor_groups=["质量"],
            alpha_score=72,
            trigger_score=64,
            risk_score=55,
            concise_summary="alpha 分 72；风险分 55",
        ),
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=116.0, high=118.0),
            stop_loss_price=114.0,
            take_profit_range=PriceRange(low=123.0, high=126.0),
            review_timeframe="daily_close_review",
            concise_summary="策略层仍以观察为主。",
        ),
    )

    assert judgement.final_action == "WATCH"
    assert judgement.key_disagreements
    assert judgement.decisive_points


def test_risk_reviewer_emits_execution_reminders() -> None:
    risk_review = build_risk_review(
        factor_profile=FactorProfileView(
            strongest_factor_groups=["趋势"],
            weakest_factor_groups=["低波动"],
            alpha_score=70,
            trigger_score=60,
            risk_score=72,
            concise_summary="风险分 72",
        ),
        technical_view=TechnicalView(
            trend_state="up",
            trigger_state="overstretched",
            key_levels=["支撑位 116.00"],
            tactical_read="价格已经偏离关键位。",
            invalidation_hint="若跌破支撑位则判断下修。",
        ),
        strategy_summary=StrategySummary(
            action="BUY",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=116.0, high=118.0),
            stop_loss_price=114.0,
            take_profit_range=PriceRange(low=123.0, high=126.0),
            review_timeframe="daily_close_review",
            concise_summary="策略允许执行。",
        ),
    )

    assert risk_review.risk_level == "high"
    assert risk_review.execution_reminders
