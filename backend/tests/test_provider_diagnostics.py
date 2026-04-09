"""Provider 诊断与健康判定测试。"""

from datetime import date
from typing import Optional

from app.schemas.market_data import DailyBar
from app.services.data_service.market_data_service import MarketDataService


class NamedDailyProvider:
    capabilities = ("daily_bars",)

    def __init__(self, name: str, *, available: bool = True) -> None:
        self.name = name
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def get_unavailable_reason(self) -> str | None:
        if self._available:
            return None
        return "mock unavailable"

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
                amount=100000.0,
                source=self.name,
            )
        ]


def test_capability_health_reports_expose_selected_provider_and_local_requirements() -> None:
    service = MarketDataService(
        providers=[
            NamedDailyProvider(name="tdx_api"),
            NamedDailyProvider(name="mootdx"),
        ]
    )

    reports = service.get_capability_health_reports()
    report_by_capability = {report.capability: report for report in reports}

    daily_report = report_by_capability["daily_bars"]
    assert daily_report.selected_provider == "tdx_api"
    assert daily_report.health_status == "degraded"
    assert daily_report.require_local_persistence is True
    assert daily_report.local_persistence_available is False
    assert "tdx_api" in daily_report.available_providers
    assert any("持久化" in item for item in daily_report.warning_messages)


def test_capability_health_report_marks_fallback_when_primary_is_unavailable() -> None:
    service = MarketDataService(
        providers=[
            NamedDailyProvider(name="tdx_api", available=False),
            NamedDailyProvider(name="mootdx"),
        ]
    )

    report = service.get_capability_health_report("daily_bars")

    assert report.selected_provider == "mootdx"
    assert report.health_status == "degraded"
    assert any("fallback" in item for item in report.warning_messages)
