"""深筛 pipeline 测试。"""

from datetime import date

from app.schemas.research import ResearchReport
from app.schemas.screener import (
    DeepScreenerRunResponse,
    ScreenerCandidate,
    ScreenerRunResponse,
)
from app.schemas.strategy import PriceRange, StrategyPlan
from app.services.data_service.exceptions import DataServiceError
from app.services.screener_service.deep_pipeline import DeepScreenerPipeline


class FakeScreenerPipeline:
    """用于深筛测试的初筛 pipeline 假对象。"""

    def run_screener(
        self,
        max_symbols: int = None,
        top_n: int = None,
    ) -> ScreenerRunResponse:
        return ScreenerRunResponse(
            as_of_date=date(2024, 3, 25),
            total_symbols=6,
            scanned_symbols=4,
            buy_candidates=[
                ScreenerCandidate(
                    symbol="600519.SH",
                    name="贵州茅台",
                    list_type="BUY_CANDIDATE",
                    rank=1,
                    screener_score=84,
                    trend_state="up",
                    trend_score=80,
                    latest_close=1688.0,
                    support_level=1620.0,
                    resistance_level=1700.0,
                    short_reason="趋势延续，量价结构稳定。",
                    predictive_score=73,
                    predictive_confidence=0.69,
                    predictive_model_version="baseline-v1",
                ),
                ScreenerCandidate(
                    symbol="300750.SZ",
                    name="宁德时代",
                    list_type="BUY_CANDIDATE",
                    rank=2,
                    screener_score=76,
                    trend_state="up",
                    trend_score=72,
                    latest_close=205.0,
                    support_level=198.0,
                    resistance_level=210.0,
                    short_reason="趋势向上，但仍需观察确认。",
                    predictive_score=66,
                    predictive_confidence=0.62,
                    predictive_model_version="baseline-v1",
                ),
            ],
            watch_candidates=[
                ScreenerCandidate(
                    symbol="000001.SZ",
                    name="平安银行",
                    list_type="WATCHLIST",
                    rank=1,
                    screener_score=65,
                    trend_state="neutral",
                    trend_score=58,
                    latest_close=11.2,
                    support_level=10.8,
                    resistance_level=11.8,
                    short_reason="通过初筛，等待方向更清晰。",
                    predictive_score=58,
                    predictive_confidence=0.57,
                    predictive_model_version="baseline-v1",
                )
            ],
            avoid_candidates=[],
        )


class FakeResearchManager:
    """用于深筛测试的研究 manager 假对象。"""

    def get_research_report(self, symbol: str) -> ResearchReport:
        if symbol == "300750.SZ":
            raise DataServiceError("mock research failure")

        if symbol == "600519.SH":
            return ResearchReport(
                symbol=symbol,
                name="贵州茅台",
                as_of_date=date(2024, 3, 25),
                technical_score=82,
                fundamental_score=78,
                event_score=64,
                risk_score=35,
                overall_score=79,
                action="BUY",
                confidence=81,
                thesis="技术和研究结论都偏积极，仍可继续跟踪买点。",
                key_reasons=["趋势保持强势"],
                risks=["短期接近压力位"],
                triggers=["回踩支撑企稳"],
                invalidations=["跌破关键支撑"],
            )

        return ResearchReport(
            symbol=symbol,
            name="平安银行",
            as_of_date=date(2024, 3, 25),
            technical_score=60,
            fundamental_score=63,
            event_score=55,
            risk_score=45,
            overall_score=61,
            action="WATCH",
            confidence=68,
            thesis="基本面平稳，但当前更适合观察。",
            key_reasons=["研究结论中性偏积极"],
            risks=["催化仍不够明确"],
            triggers=["站稳近期压力位"],
            invalidations=["跌破近期支撑"],
        )


class FakeStrategyPlanner:
    """用于深筛测试的策略 planner 假对象。"""

    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        if symbol == "600519.SH":
            return StrategyPlan(
                symbol=symbol,
                name="贵州茅台",
                as_of_date=date(2024, 3, 25),
                action="BUY",
                strategy_type="pullback",
                entry_window="next_3_to_5_trading_days",
                ideal_entry_range=PriceRange(low=1620.0, high=1660.0),
                entry_triggers=["回踩支撑后企稳"],
                avoid_if=["跌破关键支撑"],
                initial_position_hint="medium",
                stop_loss_price=1590.0,
                stop_loss_rule="跌破支撑位则止损。",
                take_profit_range=PriceRange(low=1720.0, high=1760.0),
                take_profit_rule="进入目标区间后分批止盈。",
                hold_rule="趋势未坏前继续持有。",
                sell_rule="跌破止损或趋势转弱时卖出。",
                review_timeframe="daily_close_review",
                confidence=80,
            )

        return StrategyPlan(
            symbol=symbol,
            name="平安银行",
            as_of_date=date(2024, 3, 25),
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=None,
            entry_triggers=["等待突破确认"],
            avoid_if=["趋势继续走弱"],
            initial_position_hint=None,
            stop_loss_price=None,
            stop_loss_rule="未入场前不设置止损。",
            take_profit_range=None,
            take_profit_rule="等待入场后再定义止盈。",
            hold_rule="已持有则按日线观察。",
            sell_rule="跌破支撑则卖出。",
            review_timeframe="daily_close_review",
            confidence=66,
        )


def test_run_deep_screener_returns_ranked_candidates_and_skips_failures() -> None:
    """深筛应聚合研究与策略结果，并跳过失败个股。"""
    pipeline = DeepScreenerPipeline(
        screener_pipeline=FakeScreenerPipeline(),
        research_manager=FakeResearchManager(),
        strategy_planner=FakeStrategyPlanner(),
    )

    response = pipeline.run_deep_screener(deep_top_k=3)

    assert isinstance(response, DeepScreenerRunResponse)
    assert response.total_symbols == 6
    assert response.scanned_symbols == 4
    assert response.selected_for_deep_review == 3
    assert len(response.deep_candidates) == 2
    assert response.deep_candidates[0].symbol == "600519.SH"
    assert response.deep_candidates[0].strategy_type == "pullback"
    assert response.deep_candidates[0].predictive_score == 73
    assert response.deep_candidates[0].predictive_model_version == "baseline-v1"
    assert response.deep_candidates[0].priority_score >= response.deep_candidates[1].priority_score
    assert response.deep_candidates[1].symbol == "000001.SZ"
