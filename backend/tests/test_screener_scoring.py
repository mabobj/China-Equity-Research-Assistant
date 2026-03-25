"""选股评分测试。"""

from datetime import date

from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.screener_service.scoring import score_technical_snapshot


def test_score_technical_snapshot_returns_ready_candidate_for_strong_setup() -> None:
    """强势技术结构应落入可交易候选分桶。"""
    snapshot = TechnicalSnapshot(
        symbol="600519.SH",
        as_of_date=date(2024, 3, 25),
        latest_close=1688.0,
        latest_volume=120000.0,
        moving_averages=MovingAverageSnapshot(
            ma5=1670.0,
            ma10=1660.0,
            ma20=1620.0,
            ma60=1500.0,
            ma120=1400.0,
        ),
        ema=EmaSnapshot(
            ema12=1668.0,
            ema26=1630.0,
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
        trend_score=78,
        volatility_state="normal",
        support_level=1625.0,
        resistance_level=1692.0,
    )

    result = score_technical_snapshot(snapshot)

    assert result.list_type == "BUY_CANDIDATE"
    assert result.v2_list_type == "READY_TO_BUY"
    assert result.alpha_score >= 75
    assert result.screener_score >= 70
    assert "趋势" in result.short_reason or "候选" in result.short_reason
