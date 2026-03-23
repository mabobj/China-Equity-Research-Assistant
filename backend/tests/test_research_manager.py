"""研究聚合 manager 测试。"""

from datetime import date

from app.schemas.market_data import StockProfile
from app.schemas.research import ResearchReport
from app.schemas.research_inputs import (
    AnnouncementItem,
    AnnouncementListResponse,
    FinancialSummary,
)
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.research_service.research_manager import ResearchManager


class FakeMarketDataService:
    """用于研究聚合测试的假数据服务。"""

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            source="fake",
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            revenue=1000.0,
            revenue_yoy=12.0,
            net_profit=500.0,
            net_profit_yoy=15.0,
            roe=22.0,
            gross_margin=80.0,
            debt_ratio=20.0,
            eps=5.0,
            bps=25.0,
            source="fake",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(
            symbol="600519.SH",
            count=2,
            items=[
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于股份回购进展的公告",
                    publish_date=date(2024, 3, 20),
                    announcement_type="资本运作",
                    source="fake",
                    url="https://example.com/1",
                ),
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于年度利润分配方案的公告",
                    publish_date=date(2024, 3, 18),
                    announcement_type="定期报告",
                    source="fake",
                    url="https://example.com/2",
                ),
            ],
        )


class FakeTechnicalAnalysisService:
    """用于研究聚合测试的假技术分析服务。"""

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> TechnicalSnapshot:
        return TechnicalSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 3, 25),
            latest_close=1680.0,
            latest_volume=120000.0,
            moving_averages=MovingAverageSnapshot(
                ma5=1660.0,
                ma10=1640.0,
                ma20=1600.0,
                ma60=1500.0,
                ma120=1400.0,
            ),
            ema=EmaSnapshot(
                ema12=1650.0,
                ema26=1605.0,
            ),
            macd=MacdSnapshot(
                macd=40.0,
                signal=32.0,
                histogram=8.0,
            ),
            rsi14=62.0,
            atr14=25.0,
            bollinger=BollingerSnapshot(
                middle=1600.0,
                upper=1700.0,
                lower=1500.0,
            ),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma5=110000.0,
                volume_ma20=100000.0,
                volume_ratio_to_ma5=1.09,
                volume_ratio_to_ma20=1.20,
            ),
            trend_state="up",
            trend_score=78,
            volatility_state="normal",
            support_level=1600.0,
            resistance_level=1705.0,
        )


def test_research_manager_returns_structured_report() -> None:
    """research manager 应聚合多源输入并返回结构化报告。"""
    manager = ResearchManager(
        market_data_service=FakeMarketDataService(),
        technical_analysis_service=FakeTechnicalAnalysisService(),
    )

    report = manager.get_research_report("600519")

    assert isinstance(report, ResearchReport)
    assert report.symbol == "600519.SH"
    assert report.name == "贵州茅台"
    assert report.action in {"BUY", "WATCH", "AVOID"}
    assert 0 <= report.technical_score <= 100
    assert 0 <= report.fundamental_score <= 100
    assert 0 <= report.event_score <= 100
    assert 0 <= report.risk_score <= 100
    assert 0 <= report.overall_score <= 100
    assert len(report.key_reasons) >= 1

