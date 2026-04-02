"""深筛 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_deep_screener_pipeline
from app.main import app
from app.schemas.screener import DeepScreenerCandidate, DeepScreenerRunResponse
from app.schemas.strategy import PriceRange


class StubDeepScreenerPipeline:
    """用于深筛 API 测试的 pipeline 桩对象。"""

    def run_deep_screener(
        self,
        max_symbols: int = None,
        top_n: int = None,
        deep_top_k: int = None,
    ) -> DeepScreenerRunResponse:
        return DeepScreenerRunResponse(
            as_of_date=date(2024, 3, 25),
            total_symbols=20,
            scanned_symbols=10,
            selected_for_deep_review=4,
            deep_candidates=[
                DeepScreenerCandidate(
                    symbol="600519.SH",
                    name="贵州茅台",
                    base_list_type="BUY_CANDIDATE",
                    base_rank=1,
                    base_screener_score=85,
                    research_action="BUY",
                    research_overall_score=80,
                    research_confidence=78,
                    strategy_action="BUY",
                    strategy_type="pullback",
                    ideal_entry_range=PriceRange(low=1620.0, high=1660.0),
                    stop_loss_price=1590.0,
                    take_profit_range=PriceRange(low=1720.0, high=1760.0),
                    review_timeframe="daily_close_review",
                    thesis="技术和研究结果同步偏积极。",
                    short_reason="初筛强度较高，研究与策略同时支持继续跟踪买点。",
                    priority_score=84,
                    predictive_score=72,
                    predictive_confidence=0.68,
                    predictive_model_version="baseline-v1",
                )
            ],
        )


client = TestClient(app)


def test_run_deep_screener_route_returns_structured_payload() -> None:
    """深筛接口应返回结构化响应。"""
    app.dependency_overrides[get_deep_screener_pipeline] = (
        lambda: StubDeepScreenerPipeline()
    )

    response = client.get("/screener/deep-run?max_symbols=30&top_n=10&deep_top_k=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_for_deep_review"] == 4
    assert payload["deep_candidates"][0]["symbol"] == "600519.SH"
    assert payload["deep_candidates"][0]["strategy_type"] == "pullback"
    assert payload["deep_candidates"][0]["priority_score"] == 84
    assert payload["deep_candidates"][0]["predictive_score"] == 72
    assert payload["deep_candidates"][0]["predictive_model_version"] == "baseline-v1"

    app.dependency_overrides.clear()
