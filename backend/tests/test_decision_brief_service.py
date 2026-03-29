"""Tests for decision brief builders and service."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BearCase,
    BullCase,
    ChiefJudgement,
    DebatePoint,
    DebateReviewReport,
    RiskReview,
)
from app.schemas.decision_brief import DecisionBrief
from app.schemas.factor import AlphaScore, FactorGroupScore, FactorSnapshot, RiskScore, TriggerScore
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import StockProfile
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
from app.services.decision_brief_service.decision_brief_service import DecisionBriefService
from app.services.decision_brief_service.evidence_builder import build_evidence_layer


def test_build_evidence_layer_returns_traceable_evidence() -> None:
    factor_snapshot = build_factor_snapshot()
    review_report = build_review_report()
    debate_review = build_debate_review_report()
    strategy_plan = build_strategy_plan()
    trigger_snapshot = build_trigger_snapshot()

    result = build_evidence_layer(
        factor_snapshot=factor_snapshot,
        review_report=review_report,
        debate_review=debate_review,
        strategy_plan=strategy_plan,
        trigger_snapshot=trigger_snapshot,
    )

    assert len(result.why_it_made_the_list) <= 3
    assert len(result.why_not_all_in) <= 3
    assert any(item.source_module == "factor_snapshot" for item in result.key_evidence)
    assert any(item.source_module == "review_report" for item in result.key_risks)
    assert any(item.label == "Ideal entry zone" for item in result.price_levels_to_watch)


def test_decision_brief_service_builds_actionable_summary() -> None:
    service = DecisionBriefService(
        market_data_service=StubMarketDataService(),
        technical_analysis_service=StubTechnicalAnalysisService(),
        factor_snapshot_service=StubFactorSnapshotService(),
        stock_review_service=StubStockReviewService(),
        debate_runtime_service=StubDebateRuntimeService(),
        strategy_planner=StubStrategyPlanner(),
        trigger_snapshot_service=StubTriggerSnapshotService(),
    )

    brief = service.get_decision_brief("600519.SH", use_llm=False)

    assert isinstance(brief, DecisionBrief)
    assert brief.symbol == "600519.SH"
    assert brief.action_now == "WAIT_PULLBACK"
    assert brief.conviction_level in {"low", "medium", "high"}
    assert "回踩" in brief.headline_verdict
    assert len(brief.why_it_made_the_list) <= 3
    assert len(brief.why_not_all_in) <= 3
    assert brief.next_review_window == "daily_close_review"
    assert any(item.module_name == "debate_review" for item in brief.source_modules)


class StubMarketDataService:
    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            industry="白酒",
            list_date=date(2001, 8, 27),
            status="active",
            total_market_cap=1800000000000.0,
            circulating_market_cap=1800000000000.0,
            source="stub",
        )


class StubTechnicalAnalysisService:
    def get_technical_snapshot(self, symbol: str):
        raise AssertionError("This stub should not be used when intraday snapshot succeeds.")


class StubFactorSnapshotService:
    def get_factor_snapshot(self, symbol: str) -> FactorSnapshot:
        return build_factor_snapshot()


class StubStockReviewService:
    def get_stock_review_report(self, symbol: str) -> StockReviewReport:
        return build_review_report()


class StubDebateRuntimeService:
    def get_debate_review_report(
        self,
        symbol: str,
        use_llm: bool | None = None,
    ) -> DebateReviewReport:
        return build_debate_review_report(runtime_mode="llm" if use_llm else "rule_based")


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        return build_strategy_plan()


class StubTriggerSnapshotService:
    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        return build_trigger_snapshot()

    def build_daily_fallback_trigger_snapshot(self, technical_snapshot):
        raise AssertionError("This stub should not be used when intraday snapshot succeeds.")


def build_factor_snapshot() -> FactorSnapshot:
    return FactorSnapshot(
        symbol="600519.SH",
        as_of_date=date(2024, 1, 2),
        raw_factors={},
        normalized_factors={},
        factor_group_scores=[
            FactorGroupScore(
                group_name="趋势",
                score=76.0,
                top_positive_signals=["趋势组得分较高，说明价格结构仍有韧性。"],
                top_negative_signals=[],
            ),
            FactorGroupScore(
                group_name="事件",
                score=64.0,
                top_positive_signals=["近期公告偏正向，事件温度没有转冷。"],
                top_negative_signals=[],
            ),
            FactorGroupScore(
                group_name="质量",
                score=38.0,
                top_positive_signals=[],
                top_negative_signals=["质量组分数偏弱，说明基本面把握度还不够强。"],
            ),
        ],
        alpha_score=AlphaScore(total_score=72, breakdown=[]),
        trigger_score=TriggerScore(total_score=63, trigger_state="pullback", breakdown=[]),
        risk_score=RiskScore(total_score=35, breakdown=[]),
    )


def build_review_report() -> StockReviewReport:
    return StockReviewReport(
        symbol="600519.SH",
        name="贵州茅台",
        as_of_date=date(2024, 1, 2),
        factor_profile=FactorProfileView(
            strongest_factor_groups=["趋势", "事件"],
            weakest_factor_groups=["质量"],
            alpha_score=72,
            trigger_score=63,
            risk_score=35,
            concise_summary="alpha 72，trigger 63，risk 35。",
        ),
        technical_view=TechnicalView(
            trend_state="up",
            trigger_state="near_support",
            latest_close=101.2,
            support_level=100.0,
            resistance_level=105.0,
            key_levels=["支撑位 100.00", "压力位 105.00"],
            tactical_read="价格离支撑不远，但还需要等回踩确认。",
            invalidation_hint="若后续跌破 100.00 附近支撑，当前判断需要下修。",
        ),
        fundamental_view=FundamentalView(
            quality_read="盈利质量尚可，但没有形成明显超预期。",
            growth_read="增长仍在，但斜率不够陡。",
            leverage_read="负债率总体可控。",
            data_completeness_note="部分财务字段缺失，基本面结论置信度需要下调。",
            key_financial_flags=["当前未出现明显财务红旗。"],
        ),
        event_view=EventView(
            recent_catalysts=["回购进展公告提供了偏正向的事件支撑。"],
            recent_risks=[],
            event_temperature="warm",
            concise_summary="近 30 日事件热度偏暖。",
        ),
        sentiment_view=SentimentView(
            sentiment_bias="neutral",
            crowding_hint="拥挤度中性。",
            momentum_context="短中期动量不差，但并不极端强势。",
            concise_summary="情绪中性略偏暖。",
        ),
        bull_case=BullBearCase(
            stance="bull",
            summary="有进观察名单的理由。",
            reasons=[
                "趋势与事件因子仍有支撑。",
                "支撑位附近更容易形成低风险观察点。",
            ],
        ),
        bear_case=BullBearCase(
            stance="bear",
            summary="还不能重仓的原因。",
            reasons=[
                "基本面结论仍有数据缺口。",
                "当前位置还需要等回踩确认，不适合直接追价。",
            ],
        ),
        key_disagreements=["走势偏稳，但执行位置还不够舒服。"],
        final_judgement=FinalJudgement(
            action="WATCH",
            summary="先等更好的执行位置。",
            key_points=["位置比方向更关键。"],
        ),
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=99.5, high=100.8),
            stop_loss_price=98.0,
            take_profit_range=PriceRange(low=104.0, high=107.0),
            review_timeframe="daily_close_review",
            concise_summary="先等回踩，不急着直接追价。",
        ),
        confidence=66,
    )


def build_debate_review_report(
    runtime_mode: str = "rule_based",
) -> DebateReviewReport:
    return DebateReviewReport(
        symbol="600519.SH",
        name="贵州茅台",
        as_of_date=date(2024, 1, 2),
        analyst_views=AnalystViewsBundle(
            technical=AnalystView(
                role="technical_analyst",
                summary="技术面偏向等待回踩确认。",
                action_bias="cautious",
                positive_points=[DebatePoint(title="支撑参考", detail="支撑位附近更适合观察。")],
                caution_points=[DebatePoint(title="追价风险", detail="当前位置不适合直接追价。")],
                key_levels=["支撑位 100.00", "压力位 105.00"],
            ),
            fundamental=AnalystView(
                role="fundamental_analyst",
                summary="基本面没有明显硬伤，但也没有强到足以无视位置。",
                action_bias="neutral",
                positive_points=[DebatePoint(title="财务红旗", detail="当前未出现明显财务红旗。")],
                caution_points=[DebatePoint(title="数据缺口", detail="财务字段仍有缺口。")],
                key_levels=[],
            ),
            event=AnalystView(
                role="event_analyst",
                summary="事件面偏暖。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="回购进展", detail="回购进展公告提供偏正向催化。")],
                caution_points=[],
                key_levels=[],
            ),
            sentiment=AnalystView(
                role="sentiment_analyst",
                summary="情绪中性。",
                action_bias="neutral",
                positive_points=[],
                caution_points=[DebatePoint(title="动量约束", detail="动量不差，但还不够强到直接追价。")],
                key_levels=[],
            ),
        ),
        bull_case=BullCase(
            summary="多头认为趋势和事件还在支撑这只股票。",
            reasons=[
                DebatePoint(title="趋势支撑", detail="趋势组得分仍处于相对占优区间。"),
                DebatePoint(title="事件支撑", detail="回购进展公告提供偏正向催化。"),
            ],
        ),
        bear_case=BearCase(
            summary="空头担心当前位置和信息完备度。",
            reasons=[
                DebatePoint(title="执行位置一般", detail="当前位置不适合直接追价。"),
                DebatePoint(title="信息仍不完整", detail="财务字段仍有缺口。"),
            ],
        ),
        key_disagreements=["方向不差，但执行时点还没舒服到可以直接下手。"],
        chief_judgement=ChiefJudgement(
            final_action="WATCH",
            summary="当前更适合耐心等位置。",
            decisive_points=["方向不差，但位置不便宜。"],
            key_disagreements=["方向和执行时点存在分歧。"],
        ),
        risk_review=RiskReview(
            risk_level="medium",
            summary="可以继续跟踪，但执行必须守纪律。",
            execution_reminders=["若跌破 98.00 附近风控位，应停止这轮计划。"],
        ),
        final_action="WATCH",
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=99.5, high=100.8),
            stop_loss_price=98.0,
            take_profit_range=PriceRange(low=104.0, high=107.0),
            review_timeframe="daily_close_review",
            concise_summary="先等回踩，不急着直接追价。",
        ),
        confidence=64,
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
    )


def build_strategy_plan() -> StrategyPlan:
    return StrategyPlan(
        symbol="600519.SH",
        name="贵州茅台",
        as_of_date=date(2024, 1, 2),
        action="WATCH",
        strategy_type="pullback",
        entry_window="next_3_to_5_trading_days",
        ideal_entry_range=PriceRange(low=99.5, high=100.8),
        entry_triggers=["回踩后企稳。"],
        avoid_if=["跌破支撑。"],
        initial_position_hint="small",
        stop_loss_price=98.0,
        stop_loss_rule="跌破 98.00 则退出。",
        take_profit_range=PriceRange(low=104.0, high=107.0),
        take_profit_rule="进入目标区间后分批兑现。",
        hold_rule="守住支撑则继续观察。",
        sell_rule="跌破风控位就卖出。",
        review_timeframe="daily_close_review",
        confidence=62,
    )


def build_trigger_snapshot() -> TriggerSnapshot:
    return TriggerSnapshot(
        symbol="600519.SH",
        as_of_datetime=datetime(2024, 1, 2, 14, 55, 0),
        daily_trend_state="up",
        daily_support_level=100.0,
        daily_resistance_level=105.0,
        latest_intraday_price=101.0,
        distance_to_support_pct=1.0,
        distance_to_resistance_pct=3.96,
        trigger_state="near_support",
        trigger_note="价格离支撑不远，更适合等回踩确认后再判断。",
    )
