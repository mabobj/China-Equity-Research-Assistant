"""Workflow 测试辅助构造器。"""

from __future__ import annotations

from datetime import date

from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BearCase,
    BullCase,
    ChiefJudgement,
    DebatePoint,
    DebateReviewReport,
    RiskReview,
    SingleStockResearchInputs,
)
from app.schemas.factor import (
    AlphaScore,
    FactorGroupScore,
    FactorSnapshot,
    RiskScore,
    TriggerScore,
)
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
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.schemas.strategy import PriceRange, StrategyPlan


def build_factor_snapshot(symbol: str = "600519.SH") -> FactorSnapshot:
    """构建测试用 factor snapshot。"""
    return FactorSnapshot(
        symbol=symbol,
        as_of_date=date(2024, 3, 25),
        raw_factors={"return_20d": 0.08},
        normalized_factors={"return_20d": 72.0},
        factor_group_scores=[
            FactorGroupScore(
                group_name="trend",
                score=72.0,
                top_positive_signals=["趋势保持向上"],
                top_negative_signals=[],
            )
        ],
        alpha_score=AlphaScore(total_score=73, breakdown=[]),
        trigger_score=TriggerScore(
            total_score=68,
            trigger_state="pullback",
            breakdown=[],
        ),
        risk_score=RiskScore(total_score=35, breakdown=[]),
    )


def build_stock_review_report(
    symbol: str = "600519.SH",
    name: str = "贵州茅台",
) -> StockReviewReport:
    """构建测试用个股研判报告。"""
    return StockReviewReport(
        symbol=symbol,
        name=name,
        as_of_date=date(2024, 3, 25),
        factor_profile=FactorProfileView(
            strongest_factor_groups=["趋势", "事件"],
            weakest_factor_groups=["质量"],
            alpha_score=73,
            trigger_score=68,
            risk_score=35,
            concise_summary="alpha 分 73；触发分 68；风险分 35",
        ),
        technical_view=TechnicalView(
            trend_state="up",
            trigger_state="near_breakout",
            latest_close=1688.0,
            support_level=1625.0,
            resistance_level=1692.0,
            key_levels=["支撑位 1625.00", "压力位 1692.00"],
            tactical_read="价格接近日线压力区。",
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
            momentum_context="短中期相对强弱偏正。",
            concise_summary="情绪偏多。",
        ),
        bull_case=BullBearCase(
            stance="bull",
            summary="多头论点主要来自趋势与事件。",
            reasons=["趋势占优", "事件偏正向"],
        ),
        bear_case=BullBearCase(
            stance="bear",
            summary="空头约束主要来自位置和纪律控制。",
            reasons=["靠近压力位"],
        ),
        key_disagreements=["趋势偏强，但当前触发位置并不便宜。"],
        final_judgement=FinalJudgement(
            action="WATCH",
            summary="当前更适合先观察。",
            key_points=["next_3_to_5_trading_days"],
        ),
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=100.0, high=101.0),
            stop_loss_price=98.0,
            take_profit_range=PriceRange(low=104.0, high=106.0),
            review_timeframe="daily_close_review",
            concise_summary="策略层仍以观察为主。",
        ),
        confidence=69,
    )


def build_debate_review_report(
    symbol: str = "600519.SH",
    name: str = "贵州茅台",
    runtime_mode: str = "rule_based",
) -> DebateReviewReport:
    """构建测试用 debate 报告。"""
    return DebateReviewReport(
        symbol=symbol,
        name=name,
        as_of_date=date(2024, 3, 25),
        analyst_views=AnalystViewsBundle(
            technical=AnalystView(
                role="technical_analyst",
                summary="技术偏强。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="趋势", detail="趋势偏强")],
                caution_points=[DebatePoint(title="失效条件", detail="跌破支撑位")],
                key_levels=["支撑位 1625.00"],
            ),
            fundamental=AnalystView(
                role="fundamental_analyst",
                summary="基本面中性偏稳。",
                action_bias="neutral",
                positive_points=[DebatePoint(title="质量判断", detail="盈利质量可接受")],
                caution_points=[],
                key_levels=[],
            ),
            event=AnalystView(
                role="event_analyst",
                summary="事件偏暖。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="近期催化", detail="回购公告")],
                caution_points=[],
                key_levels=[],
            ),
            sentiment=AnalystView(
                role="sentiment_analyst",
                summary="情绪偏多。",
                action_bias="supportive",
                positive_points=[DebatePoint(title="动量环境", detail="相对强弱偏正")],
                caution_points=[DebatePoint(title="拥挤度提示", detail="当前拥挤度中性")],
                key_levels=[],
            ),
        ),
        bull_case=BullCase(
            summary="多头理由主要来自趋势、事件与动量。",
            reasons=[DebatePoint(title="趋势", detail="趋势偏强")],
        ),
        bear_case=BearCase(
            summary="空头约束主要来自位置与纪律。",
            reasons=[DebatePoint(title="失效条件", detail="跌破支撑位")],
        ),
        key_disagreements=["当前分歧集中在执行时点。"],
        chief_judgement=ChiefJudgement(
            final_action="WATCH",
            summary="当前更适合先观察。",
            decisive_points=["alpha 分 73"],
            key_disagreements=["当前分歧集中在执行时点。"],
        ),
        risk_review=RiskReview(
            risk_level="medium",
            summary="风险可控但需要纪律。",
            execution_reminders=["严格观察止损参考位 98.00。"],
        ),
        final_action="WATCH",
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=100.0, high=101.0),
            stop_loss_price=98.0,
            take_profit_range=PriceRange(low=104.0, high=106.0),
            review_timeframe="daily_close_review",
            concise_summary="策略层仍以观察为主。",
        ),
        confidence=67,
        runtime_mode=runtime_mode,
    )


def build_strategy_plan(
    symbol: str = "600519.SH",
    name: str = "贵州茅台",
) -> StrategyPlan:
    """构建测试用交易策略。"""
    return StrategyPlan(
        symbol=symbol,
        name=name,
        as_of_date=date(2024, 3, 25),
        action="WATCH",
        strategy_type="wait",
        entry_window="next_3_to_5_trading_days",
        ideal_entry_range=PriceRange(low=100.0, high=101.0),
        entry_triggers=["等待有效突破或回踩确认"],
        avoid_if=["跌破日线支撑位"],
        initial_position_hint="small",
        stop_loss_price=98.0,
        stop_loss_rule="跌破 98.00 则退出观察。",
        take_profit_range=PriceRange(low=104.0, high=106.0),
        take_profit_rule="若走强则分批观察兑现。",
        hold_rule="未确认前不主动追价。",
        sell_rule="触发无效信号时退出。",
        review_timeframe="daily_close_review",
        confidence=66,
    )


def build_single_stock_research_inputs(symbol: str = "600519.SH") -> SingleStockResearchInputs:
    """构建测试用单票 workflow 起始输入。"""
    review_report = build_stock_review_report(symbol=symbol)
    return SingleStockResearchInputs(
        symbol=symbol,
        review_report=review_report,
        strategy_summary=review_report.strategy_summary,
        factor_alpha_score=73,
        factor_risk_score=35,
        trigger_state=review_report.technical_view.trigger_state,
    )


def build_screener_candidate(
    symbol: str,
    name: str,
    rank: int,
) -> ScreenerCandidate:
    """构建测试用选股候选。"""
    return ScreenerCandidate(
        symbol=symbol,
        name=name,
        list_type="BUY_CANDIDATE",
        v2_list_type="READY_TO_BUY",
        rank=rank,
        screener_score=80 - rank,
        alpha_score=78,
        trigger_score=65,
        risk_score=36,
        trend_state="up",
        trend_score=75,
        latest_close=100.0 + rank,
        support_level=98.0,
        resistance_level=105.0,
        top_positive_factors=["趋势"],
        top_negative_factors=[],
        risk_notes=[],
        short_reason="趋势保持向上。",
    )


def build_screener_run_response() -> ScreenerRunResponse:
    """构建测试用初筛结果。"""
    return ScreenerRunResponse(
        as_of_date=date(2024, 3, 25),
        total_symbols=4,
        scanned_symbols=4,
        buy_candidates=[
            build_screener_candidate("600519.SH", "贵州茅台", 1),
            build_screener_candidate("000001.SZ", "平安银行", 2),
        ],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[],
        research_only_candidates=[],
    )
