"""公告与财务摘要 API 测试。"""

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_data_service
from app.db.market_data_store import LocalMarketDataStore
from app.main import app
from app.schemas.research_inputs import (
    AnnouncementItem,
    AnnouncementListResponse,
    FinancialSummary,
)
from app.services.data_service.market_data_service import MarketDataService


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
                    announcement_type="governance",
                    announcement_subtype="board_resolution",
                    source="stub",
                    url="https://example.com/notice",
                    quality_status="ok",
                    provider_used="stub",
                    source_mode="provider_only",
                    freshness_mode="provider_fetch",
                    dedupe_key="600519.SH|2024-03-21|关于董事会决议的公告",
                    as_of_date=date(2026, 3, 27),
                )
            ],
            quality_status="ok",
            cleaning_warnings=[],
            dropped_rows=0,
            dropped_duplicate_rows=0,
            provider_used="stub",
            fallback_applied=False,
            fallback_reason=None,
            source_mode="provider_only",
            freshness_mode="provider_fetch",
            as_of_date=date(2026, 3, 27),
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            report_type="q3",
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
            quality_status="ok",
            cleaning_warnings=[],
            provider_used="stub",
            source_mode="local",
            freshness_mode="cache_preferred",
            as_of_date=date(2026, 3, 27),
        )


client = TestClient(app)


def test_get_announcements_route_returns_structured_payload() -> None:
    """公告列表接口应返回结构化与清洗摘要字段。"""
    app.dependency_overrides[get_market_data_service] = lambda: StubResearchService()
    response = client.get("/stocks/600519/announcements?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["items"][0]["announcement_type"] == "governance"
    assert payload["quality_status"] == "ok"
    assert payload["provider_used"] == "stub"
    assert payload["source_mode"] == "provider_only"
    assert payload["freshness_mode"] == "provider_fetch"
    assert payload["items"][0]["dedupe_key"] is not None

    app.dependency_overrides.clear()


def test_get_financial_summary_route_returns_structured_payload() -> None:
    """财务摘要接口应返回结构化响应。"""
    app.dependency_overrides[get_market_data_service] = lambda: StubResearchService()
    response = client.get("/stocks/sh600519/financial-summary")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["name"] == "贵州茅台"
    assert response.json()["report_type"] == "q3"
    assert response.json()["quality_status"] == "ok"
    assert response.json()["provider_used"] == "stub"
    assert response.json()["source_mode"] == "local"

    app.dependency_overrides.clear()


class _NoopFinancialProvider:
    name = "noop_financial"
    capabilities = ("financial_summary",)

    def is_available(self) -> bool:
        return True

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        return None


def test_get_financial_summary_route_backfills_report_type_and_quality(
    tmp_path: Path,
) -> None:
    """缓存旧数据缺少质量字段时，接口仍应返回可解释结果。"""
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    local_store.upsert_stock_financial_summary(
        FinancialSummary(
            symbol="600519.SH",
            name="贵州茅台",
            report_period=date(2025, 9, 30),
            source="legacy_cache",
        )
    )
    service = MarketDataService(
        providers=[_NoopFinancialProvider()],
        local_store=local_store,
    )
    app.dependency_overrides[get_market_data_service] = lambda: service

    response = client.get("/stocks/600519.SH/financial-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["report_type"] == "q3"
    assert data["quality_status"] == "degraded"
    assert "revenue" in data["missing_fields"]
    assert "net_profit" in data["missing_fields"]
    assert data["source_mode"] == "local"
    assert data["provider_used"] == "legacy_cache"

    app.dependency_overrides.clear()
