"""结构化交易策略 planner 测试。"""

from datetime import date

from app.schemas.market_data import StockProfile
from app.schemas.research import ResearchReport
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.research_service.strategy_planner import StrategyPlanner


class FakeMarketDataService:
    """用于策略测试的假市场数据服务。"""

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            source="fake",
        )


class FakeTechnicalAnalysisService:
    """用于策略测试的假技术分析服务。"""

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> TechnicalSnapshot:
        return TechnicalSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 3, 25),
            latest_close=1688.0,
            latest_volume=120000.0,
            moving_averages=MovingAverageSnapshot(
                ma5=1672.0,
                ma10=1660.0,
                ma20=1620.0,
                ma60=1510.0,
                ma120=1410.0,
            ),
            ema=EmaSnapshot(
                ema12=1668.0,
                ema26=1628.0,
            ),
            macd=MacdSnapshot(
                macd=35.0,
                signal=29.0,
                histogram=6.0,
            ),
            rsi14=61.0,
            atr14=24.0,
            bollinger=BollingerSnapshot(
                middle=1620.0,
                upper=1705.0,
                lower=1535.0,
            ),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma5=110000.0,
                volume_ma20=98000.0,
                volume_ratio_to_ma5=1.09,
                volume_ratio_to_ma20=1.22,
            ),
            trend_state="up",
            trend_score=79,
            volatility_state="normal",
            support_level=1625.0,
            resistance_level=1692.0,
        )


class FakeResearchManager:
    """用于策略测试的假研究 manager。"""

    def get_research_report(self, symbol: str) -> ResearchReport:
        return ResearchReport(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            technical_score=80,
            fundamental_score=82,
            event_score=62,
            risk_score=34,
            overall_score=77,
            action="BUY",
            confidence=74,
            thesis="当前综合判断偏积极，技术面和基本面均较稳健。",
            key_reasons=["趋势结构偏强。"],
            risks=["价格接近压力位。"],
            triggers=["有效突破压力位。"],
            invalidations=["跌破关键支撑位。"],
        )


def test_strategy_planner_returns_breakout_plan_for_strong_buy_setup() -> None:
    """强势买入情形应返回 breakout 计划。"""
    planner = StrategyPlanner(
        market_data_service=FakeMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
        research_manager=FakeResearchManager(),
    )

    plan = planner.get_strategy_plan("600519")

    assert plan.symbol == "600519.SH"
    assert plan.action == "BUY"
    assert plan.strategy_type == "breakout"
    assert plan.entry_window == "next_3_to_5_trading_days"
    assert plan.ideal_entry_range is not None
    assert plan.take_profit_range is not None
    assert plan.stop_loss_price is not None
    assert plan.initial_position_hint in {"small", "medium"}

