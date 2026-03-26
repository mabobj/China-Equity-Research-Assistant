"""LLM debate 编排器测试。"""

from __future__ import annotations

from datetime import date

from app.schemas.debate import (
    AnalystView,
    BullCase,
    ChiefJudgement,
    DebatePoint,
    RiskReview,
    SingleStockResearchInputs,
    StrategyFinalize,
    BearCase,
)
from app.schemas.review import (
    EventView,
    FactorProfileView,
    FinalJudgement,
    FundamentalView,
    SentimentView,
    StockReviewReport,
    StrategySummary,
    TechnicalView,
)
from app.schemas.strategy import PriceRange
from app.services.llm_debate_service.llm_debate_orchestrator import (
    LLMDebateOrchestrator,
)


class StubDebateOrchestrator:
    def build_inputs(self, symbol: str) -> SingleStockResearchInputs:
        return SingleStockResearchInputs(
            symbol="600519.SH",
            review_report=StockReviewReport(
                symbol="600519.SH",
                name="贵州茅台",
                as_of_date=date(2024, 3, 25),
                factor_profile=FactorProfileView(
                    strongest_factor_groups=["趋势"],
                    weakest_factor_groups=["质量"],
                    alpha_score=78,
                    trigger_score=66,
                    risk_score=35,
                    concise_summary="alpha 较强，风险可控。",
                ),
                technical_view=TechnicalView(
                    trend_state="up",
                    trigger_state="near_support",
                    key_levels=["支撑位 1660", "压力位 1710"],
                    tactical_read="价格靠近支撑位，适合观察回踩确认。",
                    invalidation_hint="若跌破支撑位则需要下修判断。",
                ),
                fundamental_view=FundamentalView(
                    quality_read="盈利质量稳健。",
                    growth_read="收入与利润保持增长。",
                    leverage_read="负债率可控。",
                    data_completeness_note="核心财务字段可用。",
                    key_financial_flags=["暂无明显财务红旗"],
                ),
                event_view=EventView(
                    recent_catalysts=["回购公告"],
                    recent_risks=["暂无明显事件风险"],
                    event_temperature="warm",
                    concise_summary="事件面偏暖。",
                ),
                sentiment_view=SentimentView(
                    sentiment_bias="bullish",
                    crowding_hint="拥挤度中性。",
                    momentum_context="20日与60日相对强弱均偏正。",
                    concise_summary="情绪偏多。",
                ),
                bull_case={
                    "stance": "bull",
                    "summary": "占位",
                    "reasons": [],
                },
                bear_case={
                    "stance": "bear",
                    "summary": "占位",
                    "reasons": [],
                },
                key_disagreements=[],
                final_judgement=FinalJudgement(
                    action="WATCH",
                    summary="先观察。",
                    key_points=["等待确认"],
                ),
                strategy_summary=StrategySummary(
                    action="WATCH",
                    strategy_type="wait",
                    entry_window="next_3_to_5_trading_days",
                    ideal_entry_range=PriceRange(low=1650.0, high=1665.0),
                    stop_loss_price=1630.0,
                    take_profit_range=PriceRange(low=1710.0, high=1740.0),
                    review_timeframe="daily_close_review",
                    concise_summary="等待更优位置。",
                ),
                confidence=70,
            ),
            strategy_summary=StrategySummary(
                action="WATCH",
                strategy_type="wait",
                entry_window="next_3_to_5_trading_days",
                ideal_entry_range=PriceRange(low=1650.0, high=1665.0),
                stop_loss_price=1630.0,
                take_profit_range=PriceRange(low=1710.0, high=1740.0),
                review_timeframe="daily_close_review",
                concise_summary="等待更优位置。",
            ),
            factor_alpha_score=78,
            factor_risk_score=35,
            trigger_state="near_support",
        )

    def finalize_strategy(
        self,
        inputs: SingleStockResearchInputs,
        chief_node,
    ) -> StrategyFinalize:
        return StrategyFinalize(
            symbol=inputs.symbol,
            final_action=chief_node.chief_judgement.final_action,
            strategy_summary=inputs.strategy_summary,
            confidence=74,
        )


class StubRoleRunner:
    def run_role(self, *, role, role_input, output_model):
        if role == "technical_analyst":
            return output_model(
                role="technical_analyst",
                summary="技术趋势偏强。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="趋势", detail="趋势向上。")],
                caution_points=[DebatePoint(title="失效", detail="跌破支撑需重估。")],
                key_levels=["支撑位 1660", "压力位 1710"],
            )
        if role == "fundamental_analyst":
            return output_model(
                role="fundamental_analyst",
                summary="基本面稳定。",
                action_bias="neutral",
                positive_points=[DebatePoint(title="质量", detail="盈利质量稳健。")],
                caution_points=[],
                key_levels=[],
            )
        if role == "event_analyst":
            return output_model(
                role="event_analyst",
                summary="事件偏暖。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="催化", detail="存在回购催化。")],
                caution_points=[],
                key_levels=[],
            )
        if role == "sentiment_analyst":
            return output_model(
                role="sentiment_analyst",
                summary="情绪偏多但不拥挤。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="动量", detail="相对强弱偏正。")],
                caution_points=[],
                key_levels=[],
            )
        if role == "bull_researcher":
            return BullCase(
                summary="做多理由较完整。",
                reasons=[DebatePoint(title="趋势", detail="趋势向上。")],
            )
        if role == "bear_researcher":
            return BearCase(
                summary="反对理由主要集中在执行位。",
                reasons=[DebatePoint(title="位置", detail="仍需等待更优买点。")],
            )
        if role == "chief_analyst":
            return ChiefJudgement(
                final_action="WATCH",
                summary="值得继续跟踪，但先等待确认。",
                decisive_points=["alpha 分数较高", "趋势仍在上行"],
                key_disagreements=["是否现在就执行"],
            )
        return RiskReview(
            risk_level="medium",
            summary="风险可控，但需要执行纪律。",
            execution_reminders=["严格观察止损位。"],
        )


def test_llm_debate_orchestrator_builds_llm_report() -> None:
    orchestrator = LLMDebateOrchestrator(
        debate_orchestrator=StubDebateOrchestrator(),
        role_runner=StubRoleRunner(),
    )

    report = orchestrator.get_debate_review_report("600519.SH")

    assert report.runtime_mode == "llm"
    assert report.symbol == "600519.SH"
    assert report.analyst_views.technical.summary == "技术趋势偏强。"
    assert report.bull_case.reasons
    assert report.chief_judgement.final_action == "WATCH"
    assert report.risk_review.risk_level == "medium"
