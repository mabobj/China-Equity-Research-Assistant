"""选股器 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_screener_pipeline
from app.main import app
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse


class StubScreenerPipeline:
    """用于选股器 API 测试的 pipeline 桩。"""

    def run_screener(
        self,
        max_symbols: int = None,
        top_n: int = None,
    ) -> ScreenerRunResponse:
        return ScreenerRunResponse(
            as_of_date=date(2024, 3, 25),
            total_symbols=3,
            scanned_symbols=2,
            buy_candidates=[
                ScreenerCandidate(
                    symbol="600519.SH",
                    name="贵州茅台",
                    list_type="BUY_CANDIDATE",
                    rank=1,
                    screener_score=82,
                    trend_state="up",
                    trend_score=79,
                    latest_close=1688.0,
                    support_level=1625.0,
                    resistance_level=1692.0,
                    short_reason="上行趋势延续，价格接近突破位，量能结构尚可。",
                )
            ],
            watch_candidates=[],
            avoid_candidates=[],
        )


client = TestClient(app)


def test_run_screener_route_returns_structured_payload() -> None:
    """选股器接口应返回结构化响应。"""
    app.dependency_overrides[get_screener_pipeline] = lambda: StubScreenerPipeline()

    response = client.get("/screener/run?max_symbols=10&top_n=5")

    assert response.status_code == 200
    assert response.json()["total_symbols"] == 3
    assert response.json()["buy_candidates"][0]["symbol"] == "600519.SH"
    assert response.json()["buy_candidates"][0]["list_type"] == "BUY_CANDIDATE"

    app.dependency_overrides.clear()
