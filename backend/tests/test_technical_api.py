"""技术分析 API 测试。"""

from datetime import date
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import get_technical_analysis_service
from app.main import app
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)


class StubTechnicalAnalysisService:
    """用于 API 测试的技术分析服务桩。"""

    def get_technical_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TechnicalSnapshot:
        return TechnicalSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 2, 9),
            latest_close=40.0,
            latest_volume=40000.0,
            moving_averages=MovingAverageSnapshot(
                ma5=38.0,
                ma10=35.5,
                ma20=30.5,
            ),
            ema=EmaSnapshot(
                ema12=36.0,
                ema26=31.0,
            ),
            macd=MacdSnapshot(
                macd=5.0,
                signal=4.2,
                histogram=0.8,
            ),
            rsi14=68.0,
            atr14=1.5,
            bollinger=BollingerSnapshot(
                middle=30.5,
                upper=41.0,
                lower=20.0,
            ),
            volume_metrics=VolumeMetricsSnapshot(
                volume_ma5=38000.0,
                volume_ma20=30000.0,
                volume_ratio_to_ma5=1.05,
                volume_ratio_to_ma20=1.33,
            ),
            trend_state="up",
            trend_score=78,
            volatility_state="normal",
            support_level=28.0,
            resistance_level=41.0,
        )


client = TestClient(app)


def test_get_technical_snapshot_route_returns_structured_payload() -> None:
    """技术分析接口应返回结构化快照。"""
    app.dependency_overrides[get_technical_analysis_service] = (
        lambda: StubTechnicalAnalysisService()
    )

    response = client.get("/stocks/600519/technical")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["trend_state"] == "up"
    assert response.json()["moving_averages"]["ma5"] == 38.0

    app.dependency_overrides.clear()


def test_invalid_symbol_on_technical_route_returns_400() -> None:
    """无效代码应返回清晰的 400 错误。"""
    app.dependency_overrides.clear()

    response = client.get("/stocks/not-a-symbol/technical")

    assert response.status_code == 400
    assert "Invalid symbol" in response.json()["detail"]
