"""研究聚合 manager 测试。"""

from datetime import date, timedelta

from app.schemas.market_data import StockProfile
from app.schemas.market_data import DailyBarResponse
from app.schemas.market_data import DailyBar
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

    def __init__(self, *, financial_quality_status: str = "ok") -> None:
        self._financial_quality_status = financial_quality_status

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            source="fake",
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        payload = FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            report_type="q3",
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
            quality_status=self._financial_quality_status,
        )
        if self._financial_quality_status == "degraded":
            return payload.model_copy(
                update={
                    "revenue": None,
                    "revenue_yoy": None,
                    "net_profit": None,
                    "net_profit_yoy": None,
                    "roe": None,
                    "missing_fields": [
                        "revenue",
                        "revenue_yoy",
                        "net_profit",
                        "net_profit_yoy",
                        "roe",
                    ],
                    "cleaning_warnings": ["关键财务字段缺失较多"],
                }
            )
        return payload

    def get_daily_bars(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> DailyBarResponse:
        start = date(2024, 1, 1)
        return DailyBarResponse(
            symbol="600519.SH",
            count=40,
            bars=[
                DailyBar(
                    symbol="600519.SH",
                    trade_date=start + timedelta(days=index),
                    open=1600.0 + index,
                    high=1610.0 + index,
                    low=1590.0 + index,
                    close=1605.0 + index,
                    volume=500000.0 + index * 1000,
                    amount=800000000.0 + index * 1000000,
                    source="fake",
                )
                for index in range(40)
            ],
            quality_status="ok",
            cleaning_warnings=[],
            dropped_rows=0,
            dropped_duplicate_rows=0,
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
            quality_status="ok",
            cleaning_warnings=[],
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

    def build_snapshot_from_bars(self, symbol: str, bars: list[DailyBar]) -> TechnicalSnapshot:
        return self.get_technical_snapshot(symbol)


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
    assert report.data_quality_summary is not None
    assert report.data_quality_summary.bars_quality == "ok"
    assert report.confidence_reasons


def test_research_manager_lowers_confidence_when_financial_quality_degraded() -> None:
    """财务质量降级应下调研究置信度并附带解释。"""
    baseline_manager = ResearchManager(
        market_data_service=FakeMarketDataService(financial_quality_status="ok"),
        technical_analysis_service=FakeTechnicalAnalysisService(),
    )
    degraded_manager = ResearchManager(
        market_data_service=FakeMarketDataService(financial_quality_status="degraded"),
        technical_analysis_service=FakeTechnicalAnalysisService(),
    )

    baseline_report = baseline_manager.get_research_report("600519")
    degraded_report = degraded_manager.get_research_report("600519")

    assert degraded_report.confidence < baseline_report.confidence
    assert degraded_report.data_quality_summary is not None
    assert degraded_report.data_quality_summary.financial_quality == "degraded"
    assert any("财务摘要质量为 degraded" in item for item in degraded_report.confidence_reasons)
    assert any("财务摘要缺失核心字段" in item for item in degraded_report.risks)
