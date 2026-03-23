"""公告与财务摘要 service 测试。"""

from datetime import date
from typing import Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.market_data_service import MarketDataService


class FakeResearchProvider:
    """用于 research input 测试的简易 fake provider。"""

    def __init__(self) -> None:
        self.name = "fake"
        self.announcement_symbol: Optional[str] = None
        self.announcement_start_date: Optional[date] = None
        self.announcement_end_date: Optional[date] = None
        self.announcement_limit: Optional[int] = None
        self.financial_symbol: Optional[str] = None

    def is_available(self) -> bool:
        return True

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        return None

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        return []

    def get_stock_universe(self) -> list[UniverseItem]:
        return []

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        self.announcement_symbol = symbol
        self.announcement_start_date = start_date
        self.announcement_end_date = end_date
        self.announcement_limit = limit
        return [
            AnnouncementItem(
                symbol=symbol,
                title="年度报告披露提示",
                publish_date=date(2024, 3, 20),
                announcement_type="定期报告",
                source=self.name,
                url="https://example.com/announcement",
            )
        ]

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        self.financial_symbol = symbol
        return FinancialSummary(
            symbol=symbol,
            name="贵州茅台",
            report_period=date(2024, 9, 30),
            revenue=100.0,
            revenue_yoy=10.0,
            net_profit=50.0,
            net_profit_yoy=12.0,
            roe=20.0,
            gross_margin=80.0,
            debt_ratio=15.0,
            eps=2.5,
            bps=12.0,
            source=self.name,
        )


def test_service_normalizes_symbol_before_fetching_announcements() -> None:
    """公告接口应在 service 层统一使用 canonical symbol。"""
    provider = FakeResearchProvider()
    service = MarketDataService(providers=[provider])

    response = service.get_stock_announcements(
        symbol="sh600519",
        start_date="2024-01-01",
        end_date="2024-03-31",
        limit=5,
    )

    assert provider.announcement_symbol == "600519.SH"
    assert provider.announcement_start_date == date(2024, 1, 1)
    assert provider.announcement_end_date == date(2024, 3, 31)
    assert provider.announcement_limit == 5
    assert response.symbol == "600519.SH"
    assert response.count == 1


def test_service_normalizes_symbol_before_fetching_financial_summary() -> None:
    """财务摘要接口应在 service 层统一使用 canonical symbol。"""
    provider = FakeResearchProvider()
    service = MarketDataService(providers=[provider])

    summary = service.get_stock_financial_summary("sz000001")

    assert provider.financial_symbol == "000001.SZ"
    assert summary.symbol == "000001.SZ"
    assert summary.name == "贵州茅台"
