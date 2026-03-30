"""daily_bars_daily 数据产品测试。"""

from datetime import date

from app.schemas.market_data import DailyBar, DailyBarResponse
from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset
from app.services.data_products.freshness import resolve_last_closed_trading_day


class _StubMarketDataService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_daily_bars(self, **kwargs) -> DailyBarResponse:
        self.calls.append(kwargs)
        as_of_date = resolve_last_closed_trading_day()
        return DailyBarResponse(
            symbol=str(kwargs["symbol"]),
            start_date=None,
            end_date=as_of_date,
            count=1,
            bars=[
                DailyBar(
                    symbol=str(kwargs["symbol"]),
                    trade_date=as_of_date,
                    open=100.0,
                    high=101.0,
                    low=99.5,
                    close=100.5,
                    volume=1000.0,
                    amount=100000.0,
                    source="mootdx",
                )
            ],
            quality_status="ok",
            cleaning_warnings=[],
            dropped_rows=0,
            dropped_duplicate_rows=0,
        )


def test_daily_bars_daily_dataset_forwards_provider_priority() -> None:
    """数据产品应透传 provider 优先级参数。"""
    market_data_service = _StubMarketDataService()
    dataset = DailyBarsDailyDataset(market_data_service=market_data_service)

    result = dataset.get(
        "600519.SH",
        force_refresh=True,
        provider_priority=("mootdx", "baostock", "akshare"),
    )

    assert result.dataset == "daily_bars_daily"
    assert result.as_of_date == resolve_last_closed_trading_day()
    assert result.payload.quality_status == "ok"
    assert len(market_data_service.calls) == 1
    assert market_data_service.calls[0]["provider_names"] == (
        "mootdx",
        "baostock",
        "akshare",
    )


def test_daily_bars_daily_dataset_keeps_cleaning_summary_in_payload() -> None:
    """清洗摘要应随 payload 返回给上层。"""
    market_data_service = _StubMarketDataService()
    dataset = DailyBarsDailyDataset(market_data_service=market_data_service)

    result = dataset.get("000001.SZ", force_refresh=False)

    assert result.payload.symbol == "000001.SZ"
    assert result.payload.quality_status == "ok"
    assert result.payload.dropped_rows == 0
    assert result.payload.cleaning_warnings == []
