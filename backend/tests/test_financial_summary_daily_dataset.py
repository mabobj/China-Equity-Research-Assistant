"""financial_summary_daily 数据产品测试。"""

from datetime import date

from app.schemas.research_inputs import FinancialSummary
from app.services.data_products.datasets.financial_summary_daily import (
    FinancialSummaryDailyDataset,
)
from app.services.data_products.freshness import resolve_last_closed_trading_day


class _StubMarketDataService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_stock_financial_summary(self, symbol: str, *, force_refresh: bool = False) -> FinancialSummary:
        self.calls.append({"symbol": symbol, "force_refresh": force_refresh})
        return FinancialSummary(
            symbol=symbol,
            name="贵州茅台",
            report_period=date(2024, 12, 31),
            report_type="annual",
            revenue=1250000000.0,
            net_profit=650000000.0,
            roe=18.6,
            debt_ratio=36.5,
            source="akshare",
            quality_status="ok",
            cleaning_warnings=[],
            provider_used="akshare",
            source_mode="provider_only",
            freshness_mode="provider_fetch",
            as_of_date=date(2026, 3, 27),
        )


def test_financial_summary_daily_dataset_uses_payload_runtime_metadata() -> None:
    """数据产品返回应优先复用 payload 自带的 freshness/source/as_of_date。"""
    market_data_service = _StubMarketDataService()
    dataset = FinancialSummaryDailyDataset(market_data_service=market_data_service)

    result = dataset.get("600519.SH", force_refresh=False)

    assert len(market_data_service.calls) == 1
    assert result.dataset == "financial_summary_daily"
    assert result.as_of_date == date(2026, 3, 27)
    assert result.freshness_mode == "provider_fetch"
    assert result.source_mode == "provider_only"
    assert result.payload.quality_status == "ok"


def test_financial_summary_daily_dataset_falls_back_when_payload_metadata_missing() -> None:
    """若 payload 缺少运行元数据，数据产品应回落到默认策略。"""

    class _FallbackStub(_StubMarketDataService):
        def get_stock_financial_summary(self, symbol: str, *, force_refresh: bool = False) -> FinancialSummary:
            self.calls.append({"symbol": symbol, "force_refresh": force_refresh})
            return FinancialSummary(
                symbol=symbol,
                name="平安银行",
                report_period=date(2024, 9, 30),
                source="akshare",
            )

    market_data_service = _FallbackStub()
    dataset = FinancialSummaryDailyDataset(market_data_service=market_data_service)

    result = dataset.get("000001.SZ", force_refresh=True)

    assert len(market_data_service.calls) == 1
    assert result.as_of_date == resolve_last_closed_trading_day()
    assert result.freshness_mode == "force_refreshed"
    assert result.source_mode == "local_plus_provider"
