from datetime import date
from pathlib import Path

from app.db.market_data_store import LocalMarketDataStore
from app.services.data_service.market_data_service import MarketDataService


class _BaseFinancialProvider:
    capabilities = ("financial_summary",)

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def is_available(self) -> bool:
        return True


class _TushareLikeProvider(_BaseFinancialProvider):
    def __init__(self) -> None:
        super().__init__("tushare")

    def get_stock_financial_summary_raw(self, symbol: str):
        self.calls += 1
        return {
            "income": {
                "end_date": "20251231",
                "total_revenue": "1000000000",
                "n_income_attr_p": "500000000",
            },
            "fina_indicator": {
                "roe": "18.6",
                "debt_to_assets": "36.5",
            },
            "source": "tushare",
        }


class _BaoStockLikeProvider(_BaseFinancialProvider):
    def __init__(self) -> None:
        super().__init__("baostock")

    def get_stock_financial_summary_raw(self, symbol: str):
        self.calls += 1
        return {
            "report_period": "2025-09-30",
            "profit": {"netProfit": "200000000"},
            "operation": {"mainBusinessRevenue": "1200000000"},
            "dupont": {"dupontROE": "11.5"},
            "balance": {"liabilityToAsset": "74.2"},
            "source": "baostock",
        }


class _FailingTushareProvider(_BaseFinancialProvider):
    def __init__(self) -> None:
        super().__init__("tushare")

    def get_stock_financial_summary_raw(self, symbol: str):
        self.calls += 1
        raise RuntimeError("mock tushare failure")


def test_financial_summary_prefers_local_store(tmp_path: Path) -> None:
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    service = MarketDataService(
        providers=[_TushareLikeProvider(), _BaoStockLikeProvider()],
        local_store=local_store,
    )
    fetched = service.get_stock_financial_summary("600519.SH", force_refresh=True)

    cached = service.get_stock_financial_summary("600519.SH")

    assert fetched.provider_used == "tushare"
    assert cached.source_mode in {"local", "provider_only", "cache_preferred"}
    assert cached.report_period == date(2025, 12, 31)


def test_financial_summary_fallbacks_from_tushare_to_baostock(tmp_path: Path) -> None:
    local_store = LocalMarketDataStore(tmp_path / "market.duckdb")
    tushare = _FailingTushareProvider()
    baostock = _BaoStockLikeProvider()
    service = MarketDataService(
        providers=[tushare, baostock],
        local_store=local_store,
    )

    summary = service.get_stock_financial_summary("000001.SZ", force_refresh=True)

    assert tushare.calls == 1
    assert baostock.calls == 1
    assert summary.provider_used == "baostock"
    assert summary.report_type == "q3"
