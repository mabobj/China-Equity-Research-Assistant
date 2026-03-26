"""个股研判 v2 service 测试。"""

from datetime import date, datetime

from app.schemas.factor import AlphaScore, FactorGroupScore, FactorSnapshot, RiskScore, TriggerScore
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import StockProfile
from app.schemas.research_inputs import AnnouncementItem, AnnouncementListResponse, FinancialSummary
from app.schemas.strategy import PriceRange, StrategyPlan
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.data_service.exceptions import ProviderError
from app.services.review_service.stock_review_service import StockReviewService


class StubMarketDataService:
    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            source="stub",
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            revenue=100.0,
            revenue_yoy=14.0,
            net_profit=30.0,
            net_profit_yoy=18.0,
            roe=20.0,
            debt_ratio=25.0,
            eps=2.5,
            source="stub",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(
            symbol="600519.SH",
            count=2,
            items=[
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于回购股份方案的公告",
                    publish_date=date(2024, 3, 20),
                    announcement_type="公司公告",
                    source="stub",
                    url="https://example.com/1",
                ),
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于中标重大合同的公告",
                    publish_date=date(2024, 3, 21),
                    announcement_type="公司公告",
                    source="stub",
                    url="https://example.com/2",
                ),
            ],
        )


class StubTechnicalAnalysisService:
    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> TechnicalSnapshot:
        return TechnicalSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 3, 25),
            latest_close=120.0,
            latest_volume=800000.0,
            moving_averages=MovingAverageSnapshot(ma20=118.0),
            ema=EmaSnapshot(ema12=119.0, ema26=117.0),
            macd=MacdSnapshot(macd=1.2, signal=0.8, histogram=0.4),
            rsi14=58.0,
            atr14=2.0,
            bollinger=BollingerSnapshot(),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma20=700000.0,
                volume_ratio_to_ma20=1.15,
            ),
            trend_state="up",
            trend_score=80,
            volatility_state="normal",
            support_level=116.0,
            resistance_level=122.0,
        )


class StubFactorSnapshotService:
    def get_factor_snapshot(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> FactorSnapshot:
        return FactorSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 3, 25),
            raw_factors={
                "return_20d": 0.12,
                "return_60d": 0.18,
                "distance_to_52w_high": -0.04,
            },
            normalized_factors={"return_20d": 72.0},
            factor_group_scores=[
                FactorGroupScore(
                    group_name="trend",
                    score=80.0,
                    top_positive_signals=["20日收益率保持正向"],
                    top_negative_signals=[],
                ),
                FactorGroupScore(
                    group_name="event",
                    score=62.0,
                    top_positive_signals=["近期公告关键词偏正向"],
                    top_negative_signals=[],
                ),
                FactorGroupScore(
                    group_name="quality",
                    score=58.0,
                    top_positive_signals=["ROE 高于常见阈值"],
                    top_negative_signals=[],
                ),
            ],
            alpha_score=AlphaScore(total_score=76, breakdown=[]),
            trigger_score=TriggerScore(total_score=68, trigger_state="pullback", breakdown=[]),
            risk_score=RiskScore(total_score=34, breakdown=[]),
        )


class StubTriggerSnapshotService:
    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        return TriggerSnapshot(
            symbol="600519.SH",
            as_of_datetime=datetime(2024, 3, 25, 10, 30, 0),
            daily_trend_state="up",
            daily_support_level=116.0,
            daily_resistance_level=122.0,
            latest_intraday_price=118.0,
            distance_to_support_pct=1.7,
            distance_to_resistance_pct=3.4,
            trigger_state="near_support",
            trigger_note="价格靠近支撑位。",
        )


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        return StrategyPlan(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            action="BUY",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=116.0, high=118.0),
            entry_triggers=["回踩企稳"],
            avoid_if=["跌破支撑"],
            initial_position_hint="small",
            stop_loss_price=114.0,
            stop_loss_rule="跌破支撑止损",
            take_profit_range=PriceRange(low=123.0, high=126.0),
            take_profit_rule="分批止盈",
            hold_rule="趋势未坏继续持有",
            sell_rule="跌破止损卖出",
            review_timeframe="daily_close_review",
            confidence=72,
        )


def test_stock_review_service_builds_review_report() -> None:
    service = StockReviewService(
        market_data_service=StubMarketDataService(),
        technical_analysis_service=StubTechnicalAnalysisService(),
        factor_snapshot_service=StubFactorSnapshotService(),
        trigger_snapshot_service=StubTriggerSnapshotService(),
        strategy_planner=StubStrategyPlanner(),
    )

    report = service.get_stock_review_report("600519.SH")

    assert report.symbol == "600519.SH"
    assert report.name == "贵州茅台"
    assert report.factor_profile.alpha_score == 76
    assert report.technical_view.trigger_state == "near_support"
    assert report.final_judgement.action == "BUY"
    assert report.strategy_summary.strategy_type == "pullback"
    assert report.confidence >= 60


class FailingTriggerSnapshotService:
    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        raise ProviderError(
            "No enabled market data providers are available for capability 'intraday_bars'."
        )

    def build_daily_fallback_trigger_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
    ) -> TriggerSnapshot:
        return TriggerSnapshot(
            symbol=technical_snapshot.symbol,
            as_of_datetime=datetime(2024, 3, 25, 15, 0, 0),
            daily_trend_state=technical_snapshot.trend_state,
            daily_support_level=technical_snapshot.support_level,
            daily_resistance_level=technical_snapshot.resistance_level,
            latest_intraday_price=technical_snapshot.latest_close,
            distance_to_support_pct=3.45,
            distance_to_resistance_pct=1.67,
            trigger_state="neutral",
            trigger_note="缺少盘中数据，使用日线降级触发判断。",
        )


def test_stock_review_service_falls_back_when_intraday_data_is_unavailable() -> None:
    service = StockReviewService(
        market_data_service=StubMarketDataService(),
        technical_analysis_service=StubTechnicalAnalysisService(),
        factor_snapshot_service=StubFactorSnapshotService(),
        trigger_snapshot_service=FailingTriggerSnapshotService(),
        strategy_planner=StubStrategyPlanner(),
    )

    report = service.get_stock_review_report("600519.SH")

    assert report.symbol == "600519.SH"
    assert report.technical_view.trigger_state == "neutral"
    assert report.technical_view.latest_close == 120.0
    assert report.technical_view.support_level == 116.0
