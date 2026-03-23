"""公告与财务摘要 API 测试。"""

from datetime import date
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_data_service
from app.main import app
from app.schemas.research_inputs import AnnouncementItem, AnnouncementListResponse, FinancialSummary


class StubResearchService:
    """用于 research input 路由测试的 stub service。"""

    def get_stock_profile(self, symbol: str) -> None:
        raise AssertionError("该测试不应调用 profile 接口。")

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> None:
        raise AssertionError("该测试不应调用 daily bars 接口。")

    def get_stock_universe(self) -> None:
        raise AssertionError("该测试不应调用 universe 接口。")

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(
            symbol="600519.SH",
            count=1,
            items=[
                AnnouncementItem(
                    symbol="600519.SH",
                    title="关于董事会决议的公告",
                    publish_date=date(2024, 3, 21),
                    announcement_type="董事会",
                    source="stub",
                    url="https://example.com/notice",
                )
            ],
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            revenue=123.0,
            revenue_yoy=9.5,
            net_profit=60.0,
            net_profit_yoy=11.0,
            roe=21.0,
            gross_margin=81.0,
            debt_ratio=16.0,
            eps=3.0,
            bps=13.0,
            source="stub",
        )


client = TestClient(app)


def test_get_announcements_route_returns_structured_payload() -> None:
    """公告列表接口应返回结构化响应。"""
    app.dependency_overrides[get_market_data_service] = lambda: StubResearchService()
    response = client.get("/stocks/600519/announcements?limit=5")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["items"][0]["announcement_type"] == "董事会"

    app.dependency_overrides.clear()


def test_get_financial_summary_route_returns_structured_payload() -> None:
    """财务摘要接口应返回结构化响应。"""
    app.dependency_overrides[get_market_data_service] = lambda: StubResearchService()
    response = client.get("/stocks/sh600519/financial-summary")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["name"] == "贵州茅台"

    app.dependency_overrides.clear()
