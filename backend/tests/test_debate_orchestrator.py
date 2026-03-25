"""角色化裁决编排器测试。"""

from datetime import date, datetime

from app.schemas.debate import DebateReviewReport
from app.schemas.factor import AlphaScore, FactorGroupScore, FactorSnapshot, RiskScore, TriggerScore
from app.schemas.intraday import TriggerSnapshot
from app.schemas.review import (
    BullBearCase,
    EventView,
    FactorProfileView,
    FinalJudgement,
    FundamentalView,
    SentimentView,
    StockReviewReport,
    StrategySummary,
    TechnicalView,
)
from app.schemas.strategy import PriceRange, StrategyPlan
from app.services.debate_service.debate_orchestrator import DebateOrchestrator


class StubStockReviewService:
    def get_stock_review_report(self, symbol: str) -> StockReviewReport:
        return StockReviewReport(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            factor_profile=FactorProfileView(
                strongest_factor_groups=["趋势", "事件"],
                weakest_factor_groups=["质量"],
                alpha_score=75,
                trigger_score=66,
                risk_score=38,
                concise_summary="alpha 分 75；触发分 66；风险分 38",
            ),
            technical_view=TechnicalView(
                trend_state="up",
                trigger_state="near_support",
                key_levels=["支撑位 116.00", "压力位 122.00"],
                tactical_read="价格靠近日线支撑区。",
                invalidation_hint="若跌破支撑位则判断下修。",
            ),
            fundamental_view=FundamentalView(
                quality_read="盈利质量处于可接受区间。",
                growth_read="收入与利润维持正增长。",
                leverage_read="负债率可控。",
                data_completeness_note="关键财务字段大体可用。",
                key_financial_flags=["当前未出现明显财务红旗"],
            ),
            event_view=EventView(
                recent_catalysts=["关于回购股份方案的公告"],
                recent_risks=[],
                event_temperature="warm",
                concise_summary="近 30 日事件热度偏暖。",
            ),
            sentiment_view=SentimentView(
                sentiment_bias="bullish",
                crowding_hint="当前拥挤度信号中性。",
                momentum_context="20 日与 60 日相对强弱均偏正。",
                concise_summary="情绪偏多。",
            ),
            bull_case=BullBearCase(stance="bull", summary="多头摘要", reasons=["趋势占优"]),
            bear_case=BullBearCase(stance="bear", summary="空头摘要", reasons=["注意压力位"]),
            key_disagreements=["时点仍有分歧"],
            final_judgement=FinalJudgement(
                action="WATCH",
                summary="当前更适合先观察。",
                key_points=["next_3_to_5_trading_days"],
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
            confidence=70,
        )


class StubFactorSnapshotService:
    def get_factor_snapshot(self, symbol: str) -> FactorSnapshot:
        return FactorSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 3, 25),
            raw_factors={},
            normalized_factors={},
            factor_group_scores=[
                FactorGroupScore(
                    group_name="trend",
                    score=78.0,
                    top_positive_signals=["趋势偏强"],
                    top_negative_signals=[],
                )
            ],
            alpha_score=AlphaScore(total_score=75, breakdown=[]),
            trigger_score=TriggerScore(total_score=66, trigger_state="pullback", breakdown=[]),
            risk_score=RiskScore(total_score=38, breakdown=[]),
        )


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        return StrategyPlan(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=116.0, high=118.0),
            entry_triggers=["等待企稳"],
            avoid_if=["跌破支撑"],
            initial_position_hint=None,
            stop_loss_price=114.0,
            stop_loss_rule="跌破支撑止损",
            take_profit_range=PriceRange(low=123.0, high=126.0),
            take_profit_rule="分批止盈",
            hold_rule="趋势未坏持有",
            sell_rule="跌破止损卖出",
            review_timeframe="daily_close_review",
            confidence=68,
        )


class StubTriggerSnapshotService:
    def get_trigger_snapshot(self, symbol: str, frequency: str = "1m", limit: int = 60) -> TriggerSnapshot:
        return TriggerSnapshot(
            symbol="600519.SH",
            as_of_datetime=datetime(2024, 3, 25, 10, 0, 0),
            daily_trend_state="up",
            daily_support_level=116.0,
            daily_resistance_level=122.0,
            latest_intraday_price=118.0,
            distance_to_support_pct=1.7,
            distance_to_resistance_pct=3.0,
            trigger_state="near_support",
            trigger_note="价格靠近支撑位。",
        )


def test_debate_orchestrator_builds_structured_report() -> None:
    orchestrator = DebateOrchestrator(
        stock_review_service=StubStockReviewService(),
        factor_snapshot_service=StubFactorSnapshotService(),
        strategy_planner=StubStrategyPlanner(),
        trigger_snapshot_service=StubTriggerSnapshotService(),
    )

    report = orchestrator.get_debate_review_report("600519.SH")

    assert isinstance(report, DebateReviewReport)
    assert report.symbol == "600519.SH"
    assert report.analyst_views.technical.role == "technical_analyst"
    assert report.bull_case.reasons
    assert report.bear_case.reasons
    assert report.chief_judgement.final_action == report.final_action
