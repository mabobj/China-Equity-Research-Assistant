"""因子快照服务测试。"""

from __future__ import annotations

from datetime import date, timedelta

from app.schemas.market_data import DailyBar, DailyBarResponse
from app.schemas.research_inputs import AnnouncementItem, AnnouncementListResponse, FinancialSummary
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.factor_service.factor_snapshot_service import FactorSnapshotService


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
            latest_volume=600000.0,
            moving_averages=MovingAverageSnapshot(ma20=118.0),
            ema=EmaSnapshot(ema12=119.0, ema26=117.0),
            macd=MacdSnapshot(macd=1.2, signal=0.8, histogram=0.4),
            rsi14=58.0,
            atr14=2.0,
            bollinger=BollingerSnapshot(),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma20=550000.0,
                volume_ratio_to_ma20=1.12,
            ),
            trend_state="up",
            trend_score=78,
            volatility_state="normal",
            support_level=116.0,
            resistance_level=122.0,
        )


class StubMarketDataService:
    def get_daily_bars(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> DailyBarResponse:
        start = date(2023, 6, 1)
        bars = [
            DailyBar(
                symbol="600519.SH",
                trade_date=start + timedelta(days=index),
                close=80.0 + index * 0.3,
                high=80.5 + index * 0.3,
                low=79.5 + index * 0.3,
                volume=500000.0 + index * 1000.0,
                amount=50_000_000.0,
                source="stub",
            )
            for index in range(260)
        ]
        return DailyBarResponse(
            symbol="600519.SH",
            count=len(bars),
            bars=bars,
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            revenue=100.0,
            revenue_yoy=16.0,
            net_profit=30.0,
            net_profit_yoy=22.0,
            roe=20.0,
            debt_ratio=25.0,
            eps=2.8,
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
                    publish_date=date(2024, 3, 22),
                    announcement_type="公司公告",
                    source="stub",
                    url="https://example.com/1",
                ),
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于中标重大合同的公告",
                    publish_date=date(2024, 3, 20),
                    announcement_type="公司公告",
                    source="stub",
                    url="https://example.com/2",
                ),
            ],
        )


def test_factor_snapshot_service_builds_structured_scores() -> None:
    """因子快照服务应输出 alpha、trigger、risk 和分组分数。"""
    service = FactorSnapshotService(
        technical_analysis_service=StubTechnicalAnalysisService(),
        market_data_service=StubMarketDataService(),
    )

    snapshot = service.get_factor_snapshot("600519.SH")

    assert snapshot.symbol == "600519.SH"
    assert snapshot.alpha_score.total_score >= 60
    assert snapshot.trigger_score.trigger_state in {"pullback", "breakout", "neutral"}
    assert snapshot.risk_score.total_score <= 60
    assert any(group.group_name == "trend" for group in snapshot.factor_group_scores)
    assert "return_20d" in snapshot.raw_factors
