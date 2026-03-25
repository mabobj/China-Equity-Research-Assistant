"""因子库单元测试。"""

from datetime import date, timedelta

from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.factor_service.factor_library.event_factors import build_event_group
from app.services.factor_service.factor_library.low_vol_factors import build_low_vol_group
from app.services.factor_service.factor_library.quality_factors import build_quality_group


def test_quality_group_scores_financial_health() -> None:
    """质量因子应能从财务摘要生成分数。"""
    group = build_quality_group(
        FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            revenue=100.0,
            revenue_yoy=15.0,
            net_profit=30.0,
            net_profit_yoy=18.0,
            roe=22.0,
            debt_ratio=28.0,
            eps=3.2,
            source="test",
        )
    )

    assert group.group_name == "quality"
    assert group.score is not None
    assert group.score > 70


def test_low_vol_group_detects_high_risk_drawdown() -> None:
    """低波动因子应识别高波动与回撤。"""
    closes = [100.0, 104.0, 98.0, 107.0, 90.0, 95.0, 88.0, 92.0] * 10
    group = build_low_vol_group(
        closes=closes,
        technical_snapshot=_build_technical_snapshot(),
    )

    assert group.group_name == "low_vol"
    assert group.score is not None
    assert group.score < 60


def test_event_group_scores_recent_positive_announcements() -> None:
    """事件因子应结合数量、关键词与新鲜度。"""
    group = build_event_group(
        announcements=[
            AnnouncementItem(
                symbol="600519.SH",
                title="关于回购股份方案的公告",
                publish_date=date(2024, 3, 20),
                announcement_type="公司公告",
                source="test",
                url="https://example.com/1",
            ),
            AnnouncementItem(
                symbol="600519.SH",
                title="关于中标重大合同的公告",
                publish_date=date(2024, 3, 22),
                announcement_type="公司公告",
                source="test",
                url="https://example.com/2",
            ),
        ],
        as_of_date=date(2024, 3, 25),
    )

    assert group.group_name == "event"
    assert group.score is not None
    assert group.score > 60


def _build_technical_snapshot() -> TechnicalSnapshot:
    return TechnicalSnapshot(
        symbol="600519.SH",
        as_of_date=date.today() - timedelta(days=1),
        latest_close=100.0,
        latest_volume=500000.0,
        moving_averages=MovingAverageSnapshot(),
        ema=EmaSnapshot(),
        macd=MacdSnapshot(),
        rsi14=55.0,
        atr14=6.0,
        bollinger=BollingerSnapshot(),
        volume_metrics=VolumeMetricsSnapshot(),
        trend_state="neutral",
        trend_score=55,
        volatility_state="high",
        support_level=95.0,
        resistance_level=105.0,
    )
