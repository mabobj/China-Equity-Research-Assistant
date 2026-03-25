"""个股研判 builder 测试。"""

from datetime import date, datetime

from app.schemas.factor import AlphaScore, FactorGroupScore, FactorSnapshot, RiskScore, TriggerScore
from app.schemas.intraday import TriggerSnapshot
from app.schemas.research_inputs import AnnouncementItem
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.review_service.event_view_builder import build_event_view
from app.services.review_service.factor_profile_builder import build_factor_profile_view
from app.services.review_service.sentiment_view_builder import build_sentiment_view


def test_factor_profile_builder_returns_ranked_groups() -> None:
    snapshot = _build_factor_snapshot()

    profile = build_factor_profile_view(snapshot)

    assert profile.alpha_score == 74
    assert profile.strongest_factor_groups[0] == "趋势"
    assert "偏弱维度" in profile.concise_summary


def test_event_view_builder_extracts_catalyst_and_risk_titles() -> None:
    snapshot = _build_factor_snapshot()
    announcements = [
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
            title="关于减持计划的公告",
            publish_date=date(2024, 3, 21),
            announcement_type="公司公告",
            source="stub",
            url="https://example.com/2",
        ),
    ]

    event_view = build_event_view(announcements, snapshot)

    assert event_view.event_temperature == "warm"
    assert any("回购" in item for item in event_view.recent_catalysts)
    assert any("减持" in item for item in event_view.recent_risks)


def test_sentiment_view_builder_marks_bullish_when_trend_and_trigger_align() -> None:
    sentiment_view = build_sentiment_view(
        factor_snapshot=_build_factor_snapshot(),
        technical_snapshot=_build_technical_snapshot(),
        trigger_snapshot=_build_trigger_snapshot(),
    )

    assert sentiment_view.sentiment_bias == "bullish"
    assert "动量" in sentiment_view.momentum_context


def _build_factor_snapshot() -> FactorSnapshot:
    return FactorSnapshot(
        symbol="600519.SH",
        as_of_date=date(2024, 3, 25),
        raw_factors={
            "return_20d": 0.12,
            "return_60d": 0.25,
            "distance_to_52w_high": -0.05,
        },
        normalized_factors={},
        factor_group_scores=[
            FactorGroupScore(
                group_name="trend",
                score=82.0,
                top_positive_signals=["20日收益率保持正向"],
                top_negative_signals=[],
            ),
            FactorGroupScore(
                group_name="event",
                score=60.0,
                top_positive_signals=["近期公告关键词偏正向"],
                top_negative_signals=[],
            ),
            FactorGroupScore(
                group_name="quality",
                score=45.0,
                top_positive_signals=[],
                top_negative_signals=["ROE 偏弱"],
            ),
        ],
        alpha_score=AlphaScore(total_score=74, breakdown=[]),
        trigger_score=TriggerScore(total_score=66, trigger_state="pullback", breakdown=[]),
        risk_score=RiskScore(total_score=38, breakdown=[]),
    )


def _build_technical_snapshot() -> TechnicalSnapshot:
    return TechnicalSnapshot(
        symbol="600519.SH",
        as_of_date=date(2024, 3, 25),
        latest_close=120.0,
        latest_volume=1_200_000.0,
        moving_averages=MovingAverageSnapshot(ma20=118.0),
        ema=EmaSnapshot(ema12=119.0, ema26=117.0),
        macd=MacdSnapshot(macd=1.0, signal=0.7, histogram=0.3),
        rsi14=58.0,
        atr14=2.0,
        bollinger=BollingerSnapshot(),
        volume_metrics=VolumeMetricsSnapshot(
            volume_ma20=900000.0,
            volume_ratio_to_ma20=1.5,
        ),
        trend_state="up",
        trend_score=78,
        volatility_state="normal",
        support_level=116.0,
        resistance_level=122.0,
    )


def _build_trigger_snapshot() -> TriggerSnapshot:
    return TriggerSnapshot(
        symbol="600519.SH",
        as_of_datetime=datetime(2024, 3, 25, 10, 30, 0),
        daily_trend_state="up",
        daily_support_level=116.0,
        daily_resistance_level=122.0,
        latest_intraday_price=118.2,
        distance_to_support_pct=1.9,
        distance_to_resistance_pct=3.2,
        trigger_state="near_support",
        trigger_note="价格靠近支撑位。",
    )
